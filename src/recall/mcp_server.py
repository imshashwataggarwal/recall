"""``recall-mcp`` — an MCP stdio server exposing Recall to Copilot / any MCP host.

The tool *logic* lives in plain functions (``mem_search``, ``mem_recent``, ...)
so it is unit-testable without an MCP runtime. ``main()`` wires those functions
into a FastMCP stdio server (requires the optional ``mcp`` dependency).
"""
from __future__ import annotations

from typing import Any

from .capture import EntryInput, append_entry
from .config import load_config
from .indexer import index_all, index_file
from .search import format_context, search
from .store import Store
from . import workstream as ws_mod


def _embedder(cfg, store):
    if not store.vec_enabled:
        return None
    from .embed import OllamaEmbedder
    return OllamaEmbedder.from_config(cfg)


def mem_search(query: str, workstream: str | None = None,
               all_workstreams: bool = False, k: int = 6) -> str:
    """Retrieve relevant prior context (decisions/tradeoffs/gotchas) as citable text."""
    cfg = load_config()
    store = Store(cfg)
    slug = None
    if workstream:
        slug = ws_mod.slugify(workstream)
    elif not all_workstreams:
        try:
            slug = ws_mod.resolve().slug
        except ValueError:
            slug = None
    hits = search(cfg, store, query, embedder=_embedder(cfg, store),
                  workstream=slug, all_workstreams=all_workstreams, k=k)
    store.close()
    return format_context(hits)


def mem_recent(workstream: str | None = None, n: int = 10) -> list[dict[str, Any]]:
    """List the most recent entries (for 'where was I?' orientation)."""
    cfg = load_config()
    store = Store(cfg)
    slug = ws_mod.slugify(workstream) if workstream else None
    if slug is None:
        try:
            slug = ws_mod.resolve().slug
        except ValueError:
            slug = None
    chunks = store.recent(slug, n)
    store.close()
    return [{"workstream": c.workstream_name, "title": c.title, "ts": c.ts,
             "status": c.status, "chunk_id": c.chunk_id} for c in chunks]


def mem_append(title: str, body: str, workstream: str | None = None,
               session: str = "", tags: list[str] | None = None,
               supersedes: list[str] | None = None) -> dict[str, str]:
    """Append a structured knowledge entry and incrementally reindex it."""
    cfg = load_config()
    ws = ws_mod.resolve(label=workstream)
    entry_id = append_entry(cfg, ws, EntryInput(
        title=title, body=body, session=session,
        tags=tags or [], supersedes=supersedes or [],
    ))
    store = Store(cfg)
    from .capture import workstream_path
    index_file(cfg, store, _embedder(cfg, store), workstream_path(cfg, ws))
    store.close()
    return {"entry_id": entry_id, "workstream": ws.name}


def mem_workstreams() -> list[dict[str, Any]]:
    """List known workstreams with entry counts."""
    cfg = load_config()
    store = Store(cfg)
    out = [{"slug": s, "name": n, "entries": c} for s, n, c in store.workstreams()]
    store.close()
    return out


def mem_index(changed_only: bool = True) -> dict[str, int]:
    """(Re)build the search index from Markdown files."""
    cfg = load_config()
    store = Store(cfg)
    res = index_all(cfg, store, _embedder(cfg, store), changed_only=changed_only)
    store.close()
    return res


def main() -> None:  # pragma: no cover - requires mcp runtime
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("recall")

    server.tool()(mem_search)
    server.tool()(mem_recent)
    server.tool()(mem_append)
    server.tool()(mem_workstreams)
    server.tool()(mem_index)

    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
