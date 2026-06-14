#!/usr/bin/env bash
# Recall — one-command installer (macOS / Linux).
#
# Usage:
#   ./scripts/install.sh                 # install from this clone
#   ./scripts/install.sh --pull-model    # also `ollama pull` the embedding model
#   curl -fsSL <raw-url>/scripts/install.sh | bash   # remote install (from git)
#
# It is idempotent: safe to re-run. It prefers pipx for a clean global install,
# otherwise falls back to a local virtualenv.
set -eu

REPO="https://github.com/imshashwataggarwal/recall.git"
MODEL="embeddinggemma"
PULL_MODEL=0
for arg in "$@"; do
  case "$arg" in
    --pull-model) PULL_MODEL=1 ;;
    *) ;;
  esac
done

note()  { printf '\033[36m=>\033[0m %s\n' "$*"; }
ok()    { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn()  { printf '\033[33m!\033[0m %s\n' "$*"; }
die()   { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# --- 1. Find Python ----------------------------------------------------------
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null; then
      PY="$c"; break
    fi
  fi
done
[ -n "$PY" ] || die "Python >= 3.10 not found. Install it from https://python.org and re-run."
ok "Using $($PY --version 2>&1) ($(command -v "$PY"))"

# --- 2. Locate the source (clone dir or remote) ------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo "")"
SOURCE_SPEC=""
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/../pyproject.toml" ]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
  SOURCE_SPEC="$REPO_ROOT"
  note "Installing from local clone: $REPO_ROOT"
else
  SOURCE_SPEC="git+$REPO"
  note "Installing from $REPO"
fi

# --- 3. Install (pipx preferred, else venv) ----------------------------------
RECALL_BIN=""
if command -v pipx >/dev/null 2>&1; then
  note "Installing with pipx…"
  if [ -d "$SOURCE_SPEC" ]; then
    pipx install --force "${SOURCE_SPEC}[mcp]" || pipx install --force "$SOURCE_SPEC"
  else
    pipx install --force "recall[mcp] @ $SOURCE_SPEC" || pipx install --force "recall @ $SOURCE_SPEC"
  fi
  RECALL_BIN="recall"
  ok "Installed via pipx"
else
  warn "pipx not found — using a local virtualenv instead."
  VENV="${RECALL_VENV:-$HOME/.recall-venv}"
  [ -d "$SOURCE_SPEC" ] && VENV="$SOURCE_SPEC/.venv"
  note "Creating venv at $VENV"
  "$PY" -m venv "$VENV"
  # shellcheck disable=SC1091
  . "$VENV/bin/activate"
  python -m pip install --upgrade pip >/dev/null
  if [ -d "$SOURCE_SPEC" ]; then
    python -m pip install -e "${SOURCE_SPEC}[mcp]"
  else
    python -m pip install "recall[mcp] @ $SOURCE_SPEC"
  fi
  RECALL_BIN="$VENV/bin/recall"
  ok "Installed into $VENV"
  warn "Add it to your PATH, e.g.:  export PATH=\"$VENV/bin:\$PATH\""
fi

# --- 4. Initialize the knowledge base ---------------------------------------
note "Initializing the knowledge base…"
"$RECALL_BIN" init

# --- 5. Optional: Ollama embedding model ------------------------------------
if command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | grep -q "$MODEL"; then
    ok "Ollama model '$MODEL' already present (semantic search enabled)."
  elif [ "$PULL_MODEL" -eq 1 ]; then
    note "Pulling Ollama model '$MODEL' (~600MB)…"
    ollama pull "$MODEL" && ok "Model pulled."
  else
    warn "Ollama found but '$MODEL' not pulled. For semantic search run: ollama pull $MODEL"
    warn "(or re-run this installer with --pull-model). Keyword (BM25) search works without it."
  fi
else
  warn "Ollama not installed — Recall will use BM25-only search."
  warn "For semantic search, install Ollama from https://ollama.com then: ollama pull $MODEL"
fi

# --- 6. Doctor + next steps --------------------------------------------------
echo
note "Running recall doctor…"
"$RECALL_BIN" doctor || true
echo
ok "Recall is installed."
cat <<EOF

Next steps:
  1. Register the MCP server in your agent (e.g. ~/.copilot/mcp-config.json):
       { "mcpServers": { "recall": { "command": "recall-mcp" } } }
  2. Try it:
       echo '### Decision   Hello, memory.' | recall append --workstream demo/test --title hello --session s1 --body -
       recall search "hello memory" --workstream demo/test
  3. Read the docs: docs/  (start with docs/installation.md and docs/mcp-and-copilot.md)
EOF
