# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0]

Initial public release — a fully-local, self-evolving personal knowledge base
that gives Copilot and any agentic CLI persistent, searchable memory.

### Added
- **Capture** — append-only, atomic, timestamped entries per workstream, with
  supersede logic so corrections never destroy history.
- **Index** — SQLite with FTS5 (BM25) + `sqlite-vec` (semantic vectors),
  incremental by content hash.
- **Retrieval** — hybrid BM25 + semantic search fused with Reciprocal Rank
  Fusion, recency decay, and superseded-entry filtering. Degrades gracefully to
  BM25-only when `sqlite-vec` or Ollama is unavailable.
- **Consolidation** — durable per-workstream summaries plus a catalog (the
  self-evolving loop).
- **`recall` CLI** — `init`, `append`, `index`, `search`, `recent`,
  `workstreams`, `consolidate`, `doctor`.
- **`recall-mcp` MCP server** — `mem_search`, `mem_recent`, `mem_append`,
  `mem_workstreams`, `mem_index`.
- **Copilot integrations** — `/mem-summarize` skill, a fail-safe session-end
  hook, and a copilot-instructions snippet (under `integrations/`).
- **Docs** — architecture, design, call-flows, installation, configuration, CLI
  reference, and MCP/Copilot integration, with Mermaid diagrams.
- **Tooling** — one-command installers (`scripts/install.sh`, `install.ps1`),
  `src/` package layout, CI workflow, MIT license, and an offline test suite
  (16 tests; `FakeEmbedder`, no network).
