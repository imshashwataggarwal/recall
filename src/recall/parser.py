"""Parse per-workstream Markdown files into atomic entries / chunks.

File shape (see capture.py for the writer)::

    # Workstream: acme/api-gateway
    <!-- recall:workstream=acme/api-gateway type=repo -->

    ## 2026-06-14 · session 97f80d49 · auth-refactor
    <!-- recall:entry id=97f80d49-1 ts=2026-06-14T15:04 tags=[auth,jwt] status=active supersedes=[] -->
    ### Decision   ...
    ### Why        ...
"""
from __future__ import annotations

import re
from pathlib import Path

from .models import Chunk, Entry
from .workstream import unslugify

_WS_RE = re.compile(r"<!--\s*recall:workstream=(?P<name>\S+)(?:\s+type=(?P<type>\S+))?\s*-->")
_ENTRY_RE = re.compile(r"<!--\s*recall:entry\s+(?P<attrs>.*?)\s*-->")
_HEADING_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)


def _parse_list_attr(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [x.strip() for x in raw.split(",") if x.strip()]


def _parse_attrs(attrs: str) -> dict[str, str]:
    """Parse ``key=value`` pairs where value may be a ``[a,b]`` list."""
    out: dict[str, str] = {}
    for m in re.finditer(r"(\w+)=(\[[^\]]*\]|\S+)", attrs):
        out[m.group(1)] = m.group(2)
    return out


def parse_workstream_header(text: str) -> tuple[str, str]:
    """Return ``(name, type)`` from the workstream header comment if present."""
    m = _WS_RE.search(text)
    if m:
        return m.group("name"), (m.group("type") or "manual")
    return "", "manual"


def parse_entries(text: str) -> list[Entry]:
    """Extract every atomic entry from a workstream file's text."""
    entries: list[Entry] = []
    # Find each entry comment and the heading immediately preceding it.
    for em in _ENTRY_RE.finditer(text):
        attrs = _parse_attrs(em.group("attrs"))
        # Title = nearest preceding "## " heading, with the
        # "{date} · session {id} · " prefix stripped back to the clean title.
        title = ""
        for hm in _HEADING_RE.finditer(text, 0, em.start()):
            title = hm.group("title")
        title = title.split(" · ")[-1].strip()
        # Body = text from end of comment to next "## " or entry comment or EOF.
        body_start = em.end()
        next_heading = _HEADING_RE.search(text, body_start)
        next_entry = _ENTRY_RE.search(text, body_start)
        ends = [e for e in (
            next_heading.start() if next_heading else None,
            next_entry.start() if next_entry else None,
        ) if e is not None]
        body_end = min(ends) if ends else len(text)
        body = text[body_start:body_end].strip()

        entries.append(Entry(
            entry_id=attrs.get("id", ""),
            ts=attrs.get("ts", ""),
            title=title,
            body=body,
            session=attrs.get("session", ""),
            tags=_parse_list_attr(attrs.get("tags", "")),
            status=attrs.get("status", "active"),
            supersedes=_parse_list_attr(attrs.get("supersedes", "")),
        ))
    return entries


def chunks_from_file(path: Path) -> list[Chunk]:
    """Parse a workstream Markdown file into context-prefixed chunks."""
    text = path.read_text(encoding="utf-8")
    ws_name, _ws_type = parse_workstream_header(text)
    slug = path.stem
    if not ws_name:
        ws_name = unslugify(slug)

    chunks: list[Chunk] = []
    for e in parse_entries(text):
        if not e.entry_id:
            continue
        prefix = f"Workstream: {ws_name}\nEntry: {e.title} ({e.ts})\n"
        if e.tags:
            prefix += f"Tags: {', '.join(e.tags)}\n"
        chunks.append(Chunk(
            chunk_id=f"{slug}:{e.entry_id}",
            workstream_slug=slug,
            workstream_name=ws_name,
            entry_id=e.entry_id,
            ts=e.ts,
            title=e.title,
            text=prefix + "\n" + e.body,
            tags=e.tags,
            status=e.status,
        ))
    return chunks
