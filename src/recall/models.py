"""Shared data models."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Entry:
    """A single atomic, timestamped knowledge entry within a workstream file."""
    entry_id: str
    ts: str                       # ISO-8601 timestamp
    title: str                    # short human title (e.g. "auth-refactor")
    body: str                     # the structured ### sections text
    session: str = ""
    tags: list[str] = field(default_factory=list)
    status: str = "active"        # active | superseded
    supersedes: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    """An indexed unit: one entry plus its workstream context, ready for search."""
    chunk_id: str                 # f"{workstream_slug}:{entry_id}"
    workstream_slug: str
    workstream_name: str
    entry_id: str
    ts: str
    title: str
    text: str                     # context-prefixed text that gets embedded/indexed
    tags: list[str] = field(default_factory=list)
    status: str = "active"


@dataclass
class SearchHit:
    chunk: Chunk
    score: float
    bm25_rank: int | None = None
    vec_rank: int | None = None
