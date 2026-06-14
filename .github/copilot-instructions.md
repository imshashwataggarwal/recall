# Copilot instructions — developing Recall

> These instructions apply to **agents and contributors working on the Recall
> codebase itself**. If you instead want to *use* Recall as a memory layer in
> another repo, copy `integrations/copilot-instructions.snippet.md` into that repo.

See [`AGENTS.md`](../AGENTS.md) for the full agent guide. Quick essentials:

## What this project is
Recall is a fully-local, self-evolving personal knowledge base. Markdown files
under `~/.recall/sessions/` are the source of truth; a SQLite index
(FTS5 BM25 + `sqlite-vec`) powers hybrid retrieval, exposed via a CLI and an MCP
server. See [`docs/architecture.md`](../docs/architecture.md).

## Layout
- `src/recall/` — the Python package (src layout).
- `tests/` — pytest suite (uses a `FakeEmbedder`; no Ollama/network needed).
- `integrations/` — Copilot wiring: session-end hook, `/mem-summarize` skill, snippet.
- `docs/` — architecture, design, call-flows, installation, configuration.

## Dev commands
```bash
pip install -e ".[mcp,dev]"   # editable install with all extras
pytest                        # run the suite (expect: 16 passed)
```

## Conventions
- **Markdown is the source of truth**; the SQLite DB is a rebuildable index.
- **Never hard-fail** on missing optional deps: degrade gracefully
  (`sqlite-vec` missing → BM25-only; Ollama down → keyword-only). Preserve this.
- Keep modules small and single-purpose; mirror the existing docstring style.
- Add/adjust tests for any behavior change. Tests must stay offline-friendly.
- Don't store secrets in Recall entries or commit them to the repo.
