"""SQLite-backed index: chunk metadata + FTS5 (BM25) + sqlite-vec (semantic).

Markdown files are the source of truth; this DB is a derived, rebuildable index.
Indexing is incremental: each workstream file's content hash is tracked, and only
changed files are re-chunked / re-embedded.

sqlite-vec is optional at runtime: if it cannot be loaded, Recall degrades
gracefully to BM25-only search (with a warning) instead of failing outright.
"""
from __future__ import annotations

import hashlib
import sqlite3
import struct
from pathlib import Path
from typing import Iterable, Sequence

from .config import Config
from .models import Chunk

try:
    import sqlite_vec  # type: ignore
    _HAVE_SQLITE_VEC = True
except Exception:  # pragma: no cover - depends on install
    sqlite_vec = None  # type: ignore
    _HAVE_SQLITE_VEC = False


def _serialize_f32(vec: Sequence[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Store:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        cfg.ensure_dirs()
        self.db = sqlite3.connect(str(cfg.db_path))
        self.db.row_factory = sqlite3.Row
        self.vec_enabled = self._try_load_vec()
        self._init_schema()

    # -- setup -----------------------------------------------------------
    def _try_load_vec(self) -> bool:
        if not _HAVE_SQLITE_VEC:
            return False
        try:
            self.db.enable_load_extension(True)
            sqlite_vec.load(self.db)
            self.db.enable_load_extension(False)
            return True
        except Exception:
            return False

    def _init_schema(self) -> None:
        c = self.db
        c.execute("""
            CREATE TABLE IF NOT EXISTS files (
                slug TEXT PRIMARY KEY,
                hash TEXT NOT NULL
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id TEXT UNIQUE NOT NULL,
                workstream_slug TEXT NOT NULL,
                workstream_name TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                ts TEXT,
                title TEXT,
                tags TEXT,
                status TEXT,
                text TEXT NOT NULL
            )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_slug ON chunks(workstream_slug)")
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks
            USING fts5(text, content='chunks', content_rowid='id')""")
        if self.vec_enabled:
            c.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks "
                f"USING vec0(embedding float[{self.cfg.embed_dim}])"
            )
        c.commit()

    # -- write -----------------------------------------------------------
    def stored_hash(self, slug: str) -> str | None:
        row = self.db.execute("SELECT hash FROM files WHERE slug=?", (slug,)).fetchone()
        return row["hash"] if row else None

    def _delete_workstream(self, slug: str) -> None:
        rows = self.db.execute(
            "SELECT id FROM chunks WHERE workstream_slug=?", (slug,)
        ).fetchall()
        ids = [r["id"] for r in rows]
        for rid in ids:
            self.db.execute("INSERT INTO fts_chunks(fts_chunks, rowid, text) "
                            "VALUES('delete', ?, (SELECT text FROM chunks WHERE id=?))",
                            (rid, rid))
            if self.vec_enabled:
                self.db.execute("DELETE FROM vec_chunks WHERE rowid=?", (rid,))
        self.db.execute("DELETE FROM chunks WHERE workstream_slug=?", (slug,))

    def upsert_workstream(self, slug: str, chunks: Sequence[Chunk],
                          embeddings: Sequence[Sequence[float]] | None,
                          new_hash: str) -> int:
        """Replace all chunks for a workstream. ``embeddings`` aligns with ``chunks``."""
        self._delete_workstream(slug)
        n = 0
        for i, ch in enumerate(chunks):
            cur = self.db.execute(
                "INSERT INTO chunks(chunk_id, workstream_slug, workstream_name, "
                "entry_id, ts, title, tags, status, text) VALUES (?,?,?,?,?,?,?,?,?)",
                (ch.chunk_id, ch.workstream_slug, ch.workstream_name, ch.entry_id,
                 ch.ts, ch.title, ",".join(ch.tags), ch.status, ch.text),
            )
            rid = cur.lastrowid
            self.db.execute(
                "INSERT INTO fts_chunks(rowid, text) VALUES (?, ?)", (rid, ch.text)
            )
            if self.vec_enabled and embeddings is not None:
                self.db.execute(
                    "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                    (rid, _serialize_f32(embeddings[i])),
                )
            n += 1
        self.db.execute(
            "INSERT INTO files(slug, hash) VALUES(?,?) "
            "ON CONFLICT(slug) DO UPDATE SET hash=excluded.hash",
            (slug, new_hash),
        )
        self.db.commit()
        return n

    # -- read ------------------------------------------------------------
    def _row_to_chunk(self, row: sqlite3.Row) -> Chunk:
        return Chunk(
            chunk_id=row["chunk_id"], workstream_slug=row["workstream_slug"],
            workstream_name=row["workstream_name"], entry_id=row["entry_id"],
            ts=row["ts"], title=row["title"],
            tags=row["tags"].split(",") if row["tags"] else [],
            status=row["status"], text=row["text"],
        )

    def bm25(self, query: str, limit: int) -> list[tuple[int, float, Chunk]]:
        try:
            rows = self.db.execute(
                "SELECT c.*, bm25(fts_chunks) AS score "
                "FROM fts_chunks JOIN chunks c ON c.id = fts_chunks.rowid "
                "WHERE fts_chunks MATCH ? ORDER BY score LIMIT ?",
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [(r["id"], r["score"], self._row_to_chunk(r)) for r in rows]

    def knn(self, embedding: Sequence[float], limit: int) -> list[tuple[int, float, Chunk]]:
        if not self.vec_enabled:
            return []
        rows = self.db.execute(
            "SELECT v.rowid AS rid, v.distance AS dist, c.* "
            "FROM vec_chunks v JOIN chunks c ON c.id = v.rowid "
            "WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
            (_serialize_f32(embedding), limit),
        ).fetchall()
        return [(r["rid"], r["dist"], self._row_to_chunk(r)) for r in rows]

    def recent(self, slug: str | None, n: int) -> list[Chunk]:
        if slug:
            rows = self.db.execute(
                "SELECT * FROM chunks WHERE workstream_slug=? ORDER BY ts DESC, id DESC LIMIT ?",
                (slug, n),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM chunks ORDER BY ts DESC, id DESC LIMIT ?", (n,)
            ).fetchall()
        return [self._row_to_chunk(r) for r in rows]

    def workstreams(self) -> list[tuple[str, str, int]]:
        rows = self.db.execute(
            "SELECT workstream_slug, workstream_name, COUNT(*) AS n "
            "FROM chunks GROUP BY workstream_slug ORDER BY n DESC"
        ).fetchall()
        return [(r["workstream_slug"], r["workstream_name"], r["n"]) for r in rows]

    def close(self) -> None:
        self.db.close()
