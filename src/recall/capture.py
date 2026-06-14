"""Append structured entries to per-workstream Markdown files.

Markdown is the source of truth. Entries are atomic, timestamped, append-only
blocks. ``supersedes`` lets a new entry retire older ones; on append we also
flip the ``status`` of superseded entries in-place so retrieval can filter them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .workstream import Workstream


@dataclass
class EntryInput:
    title: str
    body: str                       # markdown, typically ### Decision / ### Why ...
    session: str = ""
    tags: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    ts: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M")


def _today() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


def _next_entry_id(text: str, session: str) -> str:
    base = session or "entry"
    n = len(re.findall(rf"recall:entry\s+id={re.escape(base)}-\d+", text)) + 1
    return f"{base}-{n}"


def _workstream_file(cfg: Config, ws: Workstream) -> Path:
    return cfg.sessions_dir / ws.filename


def _ensure_header(text: str, ws: Workstream) -> str:
    if "recall:workstream=" in text:
        return text
    header = (
        f"# Workstream: {ws.name}\n"
        f"<!-- recall:workstream={ws.name} type={ws.type} -->\n\n"
    )
    return header + text


def _mark_superseded(text: str, ids: list[str]) -> str:
    for sid in ids:
        # Flip status=active → superseded on the matching entry comment.
        pattern = re.compile(
            rf"(<!--\s*recall:entry\s+[^>]*id={re.escape(sid)}\b[^>]*?)status=active([^>]*-->)"
        )
        text = pattern.sub(r"\1status=superseded\2", text)
    return text


def append_entry(cfg: Config, ws: Workstream, entry: EntryInput) -> str:
    """Append an entry to the workstream file. Returns the new entry id."""
    cfg.ensure_dirs()
    path = _workstream_file(cfg, ws)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    text = _ensure_header(text, ws)

    ts = entry.ts or _now_iso()
    entry_id = _next_entry_id(text, entry.session)
    tags = "[" + ",".join(entry.tags) + "]"
    sup = "[" + ",".join(entry.supersedes) + "]"

    session_part = f"session {entry.session} · " if entry.session else ""
    block = (
        f"\n## {_today()} · {session_part}{entry.title}\n"
        f"<!-- recall:entry id={entry_id} ts={ts} session={entry.session} "
        f"tags={tags} status=active supersedes={sup} -->\n"
        f"{entry.body.strip()}\n"
    )

    if entry.supersedes:
        text = _mark_superseded(text, entry.supersedes)

    path.write_text(text.rstrip() + "\n" + block, encoding="utf-8")
    return entry_id


def workstream_path(cfg: Config, ws: Workstream) -> Path:
    return _workstream_file(cfg, ws)
