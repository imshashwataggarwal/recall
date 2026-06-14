#!/usr/bin/env python3
"""Recall session-end hook — capture the final delta when a Copilot session closes.

Wire this into Copilot CLI as a session-end / stop hook. It reads a small JSON
payload (from argv[1] or stdin) describing the finished session and appends a
final entry to the relevant workstream, then incrementally reindexes.

Design goals:
- **Fail-safe & silent:** never block session shutdown; all errors are logged to
  ``~/.recall/logs/hook.log`` and the process always exits 0.
- **No duplication:** if a ``summary`` is supplied it is used verbatim; otherwise a
  minimal placeholder entry records that the session occurred.

Expected payload (all fields optional)::

    {
      "session": "97f80d49",
      "workstream": "acme/api-gateway",   // optional; else git auto-detect from cwd
      "cwd": "/path/to/repo",
      "title": "auth-refactor",
      "summary": "### Decision ...\n### Why ...",
      "tags": ["auth", "jwt"],
      "supersedes": ["97f80d49-1"]
    }
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def _log(msg: str) -> None:
    try:
        home = Path(os.environ.get("RECALL_HOME", str(Path.home() / ".recall")))
        logs = home / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / "hook.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().isoformat()} {msg}\n")
    except Exception:
        pass


def _read_payload() -> dict:
    raw = ""
    if len(sys.argv) > 1 and sys.argv[1].strip():
        raw = sys.argv[1]
    else:
        try:
            if not sys.stdin.isatty():
                raw = sys.stdin.read()
        except Exception:
            raw = ""
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        _log(f"could not parse payload: {raw[:200]!r}")
        return {}


def main() -> int:
    try:
        payload = _read_payload()

        cwd = payload.get("cwd")
        if cwd:
            try:
                os.chdir(cwd)
            except OSError:
                pass

        from recall.capture import EntryInput, append_entry, workstream_path
        from recall.config import load_config
        from recall.indexer import index_file
        from recall.store import Store
        from recall import workstream as ws_mod

        cfg = load_config()
        try:
            ws = ws_mod.resolve(label=payload.get("workstream"))
        except ValueError:
            _log("no workstream (not a git repo and no label); skipping.")
            return 0

        session = payload.get("session", "")
        summary = payload.get("summary")
        if not summary:
            summary = "### Note   Session ended; no explicit summary captured."

        entry_id = append_entry(cfg, ws, EntryInput(
            title=payload.get("title") or f"session-{session or 'close'}",
            body=summary, session=session,
            tags=payload.get("tags") or [],
            supersedes=payload.get("supersedes") or [],
        ))

        store = Store(cfg)
        embedder = None
        if store.vec_enabled:
            try:
                from recall.embed import OllamaEmbedder
                embedder = OllamaEmbedder.from_config(cfg)
            except Exception:
                embedder = None
        index_file(cfg, store, embedder, workstream_path(cfg, ws))
        store.close()
        _log(f"captured {entry_id} for {ws.name}")
    except Exception:
        _log("hook error:\n" + traceback.format_exc())
    return 0  # never fail the session shutdown


if __name__ == "__main__":
    sys.exit(main())
