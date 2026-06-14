# Contributing to Recall

Thanks for your interest! Recall is a small, focused project — contributions that
keep it lean, local-first, and resilient are very welcome.

## Development setup

```bash
git clone <your-fork-url> recall && cd recall
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[mcp,dev]"
pytest            # expect: 16 passed
```

Tests are **offline** — they use a deterministic `FakeEmbedder` and an isolated
`RECALL_HOME`. No Ollama or network access required. Please keep new tests offline.

## Project structure

See [AGENTS.md](AGENTS.md) and [docs/architecture.md](docs/architecture.md) for the
layout and module map. In short: the package lives in `src/recall/`, tests in
`tests/`, docs in `docs/`.

## Ground rules (invariants)

These are the things that make Recall *Recall*. Please preserve them:

1. **Markdown is the source of truth.** The SQLite index must stay fully
   rebuildable from the Markdown (`recall index --full`).
2. **Never hard-fail on optional dependencies.** Missing `sqlite-vec` → BM25-only;
   Ollama down → keyword-only. Catch and degrade gracefully.
3. **Append-only history.** Supersession flips `status`; it never deletes entries.
4. **Local-first & private.** No new network calls except to a user's local Ollama.
   No telemetry. No cloud dependencies.

## Making a change

1. Open an issue first for anything non-trivial, so we can align on approach.
2. Branch from `master`.
3. Make the change in `src/recall/...` with a matching test.
4. Run `pytest`. For capture/index/search changes, also do a manual CLI smoke test
   under an isolated `RECALL_HOME`.
5. Update the relevant doc in `docs/` if you changed behavior, flags, or schema.
6. Keep commits focused; write a clear message.

## Style

- Match the existing concise docstring style; keep modules single-purpose.
- No required linter/formatter is enforced, but keep imports tidy and lines
  reasonable. Prefer standard library over new dependencies.
- Don't add a dependency without a clear, discussed reason.

## Reporting bugs

Include: OS, Python version, `recall doctor` output, the command you ran, and what
you expected vs. got. Never paste secrets.

## License

By contributing, you agree your contributions are licensed under the
[MIT License](LICENSE).
