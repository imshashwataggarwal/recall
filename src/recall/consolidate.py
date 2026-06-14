"""Consolidation: keep the KB evolving rather than just growing.

- Distill each workstream's *active* entries into an always-injectable
  ``{slug}.summary.md`` (Tier-1 durable memory).
- Report likely-stale (superseded) entries.

Distillation here is deterministic/extractive (no LLM needed) so it runs fully
offline; an LLM can later be layered on for abstractive summaries.
"""
from __future__ import annotations

from pathlib import Path

from .config import Config
from .parser import chunks_from_file


def consolidate(cfg: Config) -> dict[str, int]:
    cfg.ensure_dirs()
    written: dict[str, int] = {}
    for path in sorted(cfg.sessions_dir.glob("*.md")):
        if path.name.startswith("_") or path.name.endswith(".summary.md"):
            continue
        chunks = chunks_from_file(path)
        active = [c for c in chunks if c.status == "active"]
        if not active:
            continue
        name = active[0].workstream_name
        lines = [f"# {name} — durable summary",
                 "<!-- recall:generated=consolidate -->", ""]
        for c in active:
            tag = f" _({', '.join(c.tags)})_" if c.tags else ""
            lines.append(f"## {c.title} — {c.ts}{tag}")
            lines.append(c.text.split("\n", 2)[-1].strip())  # drop context prefix
            lines.append("")
        out = path.with_name(f"{path.stem}.summary.md")
        out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        written[path.stem] = len(active)
    _write_catalog(cfg)
    return written


def _write_catalog(cfg: Config) -> None:
    lines = ["# Recall — workstream catalog", ""]
    for path in sorted(cfg.sessions_dir.glob("*.md")):
        if path.name.startswith("_") or path.name.endswith(".summary.md"):
            continue
        chunks = chunks_from_file(path)
        if not chunks:
            continue
        name = chunks[0].workstream_name
        lines.append(f"- **{name}** — {len(chunks)} entries (`{path.name}`)")
    (cfg.sessions_dir / "_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
