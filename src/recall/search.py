"""Hybrid retrieval: BM25 (FTS5) + semantic (sqlite-vec) fused with Reciprocal
Rank Fusion, then filtered by workstream/status and re-weighted by recency.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Sequence

from .config import Config
from .models import Chunk, SearchHit
from .store import Store


class Embedder:  # structural; real one is OllamaEmbedder
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def _recency_weight(ts: str, half_life_days: float) -> float:
    """Exponential decay in [~0, 1]; newer entries score higher."""
    if not ts:
        return 0.7
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(ts, fmt)
            break
        except ValueError:
            continue
    else:
        return 0.7
    age_days = max(0.0, (datetime.now() - dt).total_seconds() / 86400.0)
    return 0.5 ** (age_days / max(1e-6, half_life_days))


def _rrf(rank: int, k: int) -> float:
    return 1.0 / (k + rank)


def search(cfg: Config, store: Store, query: str,
           embedder: Embedder | None = None,
           workstream: str | None = None, all_workstreams: bool = False,
           k: int | None = None, include_superseded: bool = False) -> list[SearchHit]:
    k = k or cfg.top_k
    pool = max(k * 5, 25)

    bm25_hits = store.bm25(_fts_query(query), pool)

    vec_hits: list = []
    if embedder is not None and store.vec_enabled:
        try:
            qvec = embedder.embed([query])[0]
            vec_hits = store.knn(qvec, pool)
        except Exception:
            vec_hits = []

    # Reciprocal Rank Fusion across the two ranked lists.
    fused: dict[int, dict] = {}
    for rank, (rid, _score, ch) in enumerate(bm25_hits, start=1):
        fused.setdefault(rid, {"chunk": ch, "score": 0.0, "bm25": None, "vec": None})
        fused[rid]["score"] += _rrf(rank, cfg.rrf_k)
        fused[rid]["bm25"] = rank
    for rank, (rid, _dist, ch) in enumerate(vec_hits, start=1):
        fused.setdefault(rid, {"chunk": ch, "score": 0.0, "bm25": None, "vec": None})
        fused[rid]["score"] += _rrf(rank, cfg.rrf_k)
        fused[rid]["vec"] = rank

    hits: list[SearchHit] = []
    for info in fused.values():
        ch: Chunk = info["chunk"]
        if not include_superseded and ch.status == "superseded":
            continue
        if not all_workstreams and workstream and ch.workstream_slug != workstream:
            continue
        weight = _recency_weight(ch.ts, cfg.recency_half_life_days)
        final = info["score"] * (0.6 + 0.4 * weight)  # blend relevance + recency
        hits.append(SearchHit(chunk=ch, score=final,
                              bm25_rank=info["bm25"], vec_rank=info["vec"]))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:k]


def _fts_query(query: str) -> str:
    """Make a forgiving FTS5 MATCH string: OR the terms, ignore punctuation."""
    import re
    terms = re.findall(r"\w+", query.lower())
    if not terms:
        return '""'
    return " OR ".join(terms)


def format_context(hits: Sequence[SearchHit]) -> str:
    """Render hits as grounded, citable context for an LLM."""
    if not hits:
        return "No relevant prior context found in Recall."
    out = ["# Relevant context from Recall (personal memory)\n"]
    for i, h in enumerate(hits, 1):
        c = h.chunk
        out.append(
            f"## [{i}] {c.workstream_name} — {c.title} ({c.ts})\n"
            f"<!-- cite: {c.chunk_id} | score={h.score:.4f} -->\n"
            f"{c.text}\n"
        )
    return "\n".join(out)
