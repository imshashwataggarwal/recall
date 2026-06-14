"""Indexing pipeline: Markdown files → chunks → (embeddings) → SQLite index.

Incremental by file content hash. Embeddings are optional: when the embedder is
unavailable, chunks are still indexed for BM25 search.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from .config import Config
from .models import Chunk
from .parser import chunks_from_file
from .store import Store, file_hash


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def _embed_chunks(embedder: Embedder | None, chunks: Sequence[Chunk]):
    if embedder is None or not chunks:
        return None
    try:
        return embedder.embed([c.text for c in chunks])
    except Exception:
        # Degrade to BM25-only indexing rather than failing the whole run.
        return None


def index_all(cfg: Config, store: Store, embedder: Embedder | None,
              changed_only: bool = True) -> dict[str, int]:
    """Index every workstream file. Returns ``{slug: chunks_indexed}``."""
    results: dict[str, int] = {}
    for path in sorted(cfg.sessions_dir.glob("*.md")):
        if path.name.startswith("_"):
            continue
        results.update(index_file(cfg, store, embedder, path, changed_only))
    return results


def index_file(cfg: Config, store: Store, embedder: Embedder | None,
               path: Path, changed_only: bool = True) -> dict[str, int]:
    slug = path.stem
    new_hash = file_hash(path)
    if changed_only and store.stored_hash(slug) == new_hash:
        return {}
    chunks = chunks_from_file(path)
    embeddings = _embed_chunks(embedder, chunks) if store.vec_enabled else None
    n = store.upsert_workstream(slug, chunks, embeddings, new_hash)
    return {slug: n}
