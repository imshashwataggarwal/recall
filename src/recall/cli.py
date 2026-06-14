"""``recall`` command-line interface.

Subcommands:
    init          Write a default config and create the KB layout.
    append        Append a structured entry to a workstream (used by skill/hook).
    index         (Re)build the search index from Markdown files.
    search        Hybrid BM25 + semantic retrieval, printed as citable context.
    recent        Show the latest entries for a workstream.
    workstreams   List known workstreams.
    consolidate   Distill durable per-workstream summaries + catalog.
    doctor        Diagnose config / Ollama / sqlite-vec availability.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import workstream as ws_mod
from .capture import EntryInput, append_entry, workstream_path
from .config import DEFAULT_CONFIG_TOML, load_config
from .consolidate import consolidate
from .indexer import index_all
from .search import format_context, search
from .store import Store


def _embedder(cfg):
    from .embed import OllamaEmbedder
    return OllamaEmbedder.from_config(cfg)


def _resolve_ws(args):
    return ws_mod.resolve(label=getattr(args, "workstream", None),
                          type_hint=getattr(args, "type", None))


def cmd_init(args) -> int:
    cfg = load_config()
    cfg.ensure_dirs()
    cfg_path = cfg.home / "config.toml"
    if not cfg_path.exists():
        cfg_path.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
    print(f"Recall initialized at {cfg.home}")
    return 0


def cmd_append(args) -> int:
    cfg = load_config()
    ws = _resolve_ws(args)
    body = args.body
    if body == "-" or body is None:
        body = sys.stdin.read()
    entry_id = append_entry(cfg, ws, EntryInput(
        title=args.title, body=body, session=args.session or "",
        tags=[t for t in (args.tags or "").split(",") if t],
        supersedes=[s for s in (args.supersedes or "").split(",") if s],
    ))
    print(f"Appended {entry_id} to {workstream_path(cfg, ws)}")
    if not args.no_index:
        store = Store(cfg)
        from .indexer import index_file
        index_file(cfg, store, _safe_embedder(cfg, store), workstream_path(cfg, ws))
        store.close()
    return 0


def _safe_embedder(cfg, store):
    return _embedder(cfg) if store.vec_enabled else None


def cmd_index(args) -> int:
    cfg = load_config()
    store = Store(cfg)
    res = index_all(cfg, store, _safe_embedder(cfg, store),
                    changed_only=not args.full)
    store.close()
    total = sum(res.values())
    if not store.vec_enabled:
        print("(note: sqlite-vec unavailable — BM25-only index)", file=sys.stderr)
    print(f"Indexed {total} chunks across {len(res)} changed workstream(s).")
    return 0


def cmd_search(args) -> int:
    cfg = load_config()
    store = Store(cfg)
    ws_slug = None
    if not args.all:
        try:
            ws_slug = _resolve_ws(args).slug
        except ValueError:
            ws_slug = None
    embedder = _safe_embedder(cfg, store)
    hits = search(cfg, store, args.query, embedder=embedder,
                  workstream=ws_slug, all_workstreams=args.all, k=args.k)
    store.close()
    if args.json:
        print(json.dumps([{
            "chunk_id": h.chunk.chunk_id, "workstream": h.chunk.workstream_name,
            "title": h.chunk.title, "ts": h.chunk.ts, "score": h.score,
            "text": h.chunk.text,
        } for h in hits], indent=2))
    else:
        print(format_context(hits))
    return 0


def cmd_recent(args) -> int:
    cfg = load_config()
    store = Store(cfg)
    slug = None
    if not args.all:
        try:
            slug = _resolve_ws(args).slug
        except ValueError:
            slug = None
    chunks = store.recent(slug, args.n)
    store.close()
    for c in chunks:
        print(f"[{c.ts}] {c.workstream_name} — {c.title}  ({c.status})")
    return 0


def cmd_workstreams(args) -> int:
    cfg = load_config()
    store = Store(cfg)
    for slug, name, n in store.workstreams():
        print(f"{n:>4}  {name}  ({slug})")
    store.close()
    return 0


def cmd_consolidate(args) -> int:
    cfg = load_config()
    res = consolidate(cfg)
    print(f"Wrote {len(res)} summary file(s).")
    return 0


def cmd_doctor(args) -> int:
    cfg = load_config()
    store = Store(cfg)
    print(f"home:          {cfg.home}")
    print(f"db:            {cfg.db_path}")
    print(f"sqlite-vec:    {'enabled' if store.vec_enabled else 'UNAVAILABLE (BM25-only)'}")
    print(f"embed model:   {cfg.embed_model} @ {cfg.ollama_host}")
    ok = False
    try:
        from .embed import OllamaEmbedder
        OllamaEmbedder.from_config(cfg).embed(["ping"])
        ok = True
    except Exception as exc:
        print(f"ollama:        DOWN ({exc})")
    if ok:
        print("ollama:        reachable ✓")
    store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="recall", description="Personal evolving knowledge base.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_ws(sp):
        sp.add_argument("--workstream", help="Explicit workstream label (else git auto-detect).")
        sp.add_argument("--type", help="Workstream type hint (repo|research|writing|ops|...).")

    sp = sub.add_parser("init"); sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("append"); add_ws(sp)
    sp.add_argument("--title", required=True)
    sp.add_argument("--body", default="-", help="Entry body markdown, or '-' for stdin.")
    sp.add_argument("--session", default="")
    sp.add_argument("--tags", default="")
    sp.add_argument("--supersedes", default="")
    sp.add_argument("--no-index", action="store_true")
    sp.set_defaults(func=cmd_append)

    sp = sub.add_parser("index")
    sp.add_argument("--full", action="store_true", help="Reindex all files, ignore hashes.")
    sp.set_defaults(func=cmd_index)

    sp = sub.add_parser("search"); add_ws(sp)
    sp.add_argument("query")
    sp.add_argument("--all", action="store_true", help="Search across all workstreams.")
    sp.add_argument("-k", type=int, default=None)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("recent"); add_ws(sp)
    sp.add_argument("-n", type=int, default=10)
    sp.add_argument("--all", action="store_true")
    sp.set_defaults(func=cmd_recent)

    sp = sub.add_parser("workstreams"); sp.set_defaults(func=cmd_workstreams)
    sp = sub.add_parser("consolidate"); sp.set_defaults(func=cmd_consolidate)
    sp = sub.add_parser("doctor"); sp.set_defaults(func=cmd_doctor)
    return p


def _force_utf8_output() -> None:
    """Avoid UnicodeEncodeError on legacy Windows consoles (cp1252).

    Entry titles, workstream names, and a few status glyphs can contain
    non-ASCII characters; reconfigure stdout/stderr so printing them never
    crashes regardless of the host console's code page.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
