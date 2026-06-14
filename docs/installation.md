# Installation

Recall is pure-Python and installs in seconds. The only optional piece is
[Ollama](https://ollama.com) for the *semantic* half of search — keyword (BM25)
search works without it.

## TL;DR (one command)

From a clone of the repo:

**macOS / Linux**
```bash
./scripts/install.sh
```

**Windows (PowerShell)**
```powershell
./scripts/install.ps1
```

The installer will: find a suitable Python, create an isolated environment
(prefers [`pipx`](https://pipx.pypa.io) if present, else a local `.venv`),
install Recall with the `mcp` extra, run `recall init`, and print a `recall doctor`
report plus next steps. Re-running it is safe (idempotent).

### One-line remote install (after the repo is published)
```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/imshashwataggarwal/recall/main/scripts/install.sh | bash
```
```powershell
# Windows
irm https://raw.githubusercontent.com/imshashwataggarwal/recall/main/scripts/install.ps1 | iex
```

## Requirements

| Requirement | Needed for | Notes |
|-------------|-----------|-------|
| Python ≥ 3.10 | everything | `python3 --version` |
| pip | install | bundled with Python |
| `sqlite-vec` | semantic vectors | installed automatically; if it can't load, Recall is BM25-only |
| Ollama + an embedding model | semantic search | optional; install from https://ollama.com |
| `pipx` | clean global install | optional; the script falls back to a venv |

## Manual install

```bash
# 1. (recommended) isolate
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1

# 2. install (add ,dev for the test suite)
pip install -e ".[mcp]"

# 3. initialize the knowledge base
recall init                          # creates ~/.recall/{config.toml,sessions,index,logs}

# 4. (optional) enable semantic search
#    install Ollama from https://ollama.com, then:
ollama pull embeddinggemma

# 5. verify
recall doctor
```

### Global install with pipx (recommended for daily use)
```bash
pipx install "git+https://github.com/imshashwataggarwal/recall.git#egg=recall[mcp]"
recall init && recall doctor
```
`pipx` puts `recall` and `recall-mcp` on your PATH in their own isolated env.

## Verifying the install

```bash
recall doctor
```
Expected (semantic enabled):
```
home:          /Users/you/.recall
db:            /Users/you/.recall/index/recall.db
sqlite-vec:    enabled
embed model:   embeddinggemma @ http://localhost:11434
ollama:        reachable ✓
```
If Ollama isn't running you'll see `ollama: DOWN (...)` and `sqlite-vec: enabled`
— that's fine; BM25 search still works.

Quick smoke test:
```bash
echo '### Decision   Test entry.' | recall append --workstream demo/test --title hello --session s1 --body -
recall index
recall search "test entry" --workstream demo/test
```

## Platform notes

### Windows
- If `python` opens the Microsoft Store, install real Python from
  https://python.org or `winget install Python.Python.3.12`, then reopen the shell.
- Run scripts with `./scripts/install.ps1`. If blocked by execution policy:
  `powershell -ExecutionPolicy Bypass -File scripts/install.ps1`.

### macOS / Linux
- `sqlite-vec` ships prebuilt wheels for common platforms; no compiler needed.
- Ollama runs as a background service after install; `ollama serve` starts it
  manually if needed.

## Running the test suite
```bash
pip install -e ".[mcp,dev]"
pytest            # expect: 16 passed
```
Tests use a deterministic `FakeEmbedder` and an isolated `RECALL_HOME`, so they
need neither Ollama nor a network connection.

## Uninstall
```bash
pipx uninstall recall          # or just delete the .venv
rm -rf ~/.recall               # removes the knowledge base too (irreversible)
```

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `sqlite-vec: UNAVAILABLE (BM25-only)` | The extension couldn't load on your platform. Search still works (keyword only). |
| `ollama: DOWN` | Ollama isn't running or the model isn't pulled. `ollama serve` + `ollama pull embeddinggemma`. |
| `Could not auto-detect a git workstream` | You're not in a git repo. Pass `--workstream <label>`. |
| `recall: command not found` | Activate your venv, or use `pipx`, or run `python -m recall.cli`. |
| Search returns nothing after append | Run `recall index` (append auto-indexes unless `--no-index`). |
