# CLI reference

Every `recall` subcommand, its flags, and examples. Run `recall <cmd> -h` for the
built-in help. If `recall` isn't on your PATH, use `python -m recall.cli`.

## Global shape
```
recall <command> [options]
```
Commands: `init`, `append`, `index`, `search`, `recent`, `workstreams`,
`consolidate`, `doctor`.

### Workstream resolution (shared by several commands)
Commands that touch a workstream accept:
- `--workstream <label>` — explicit label (e.g. `research/rag-eval`).
- `--type <hint>` — type hint (`repo` | `research` | `writing` | `ops` | ...).

If `--workstream` is omitted, Recall auto-detects from git:
`remote.origin.url` → `owner/repo`, else the repo's top-level dir name. Outside a
git repo with no label, the command either errors (append) or falls back to
all-workstreams (search/recent).

---

## `recall init`
Create the KB layout and a default `config.toml` (no-op if it already exists).
```bash
recall init
# → Recall initialized at /Users/you/.recall
```

## `recall append`
Append a structured entry to a workstream file (and incrementally index it).

| Flag | Default | Meaning |
|------|---------|---------|
| `--title` | *(required)* | Short human title for the entry. |
| `--body` | `-` | Entry markdown body; `-` reads from **stdin**. |
| `--session` | `""` | Short session id; entry ids become `<session>-<n>`. |
| `--tags` | `""` | Comma-separated tags, e.g. `auth,jwt`. |
| `--supersedes` | `""` | Comma-separated entry ids this entry retires. |
| `--no-index` | off | Skip the automatic reindex after appending. |
| `--workstream`, `--type` | auto | See resolution above. |

```bash
recall append --title auth-refactor --session 97f80d49 --tags auth,jwt --body - <<'EOF'
### Decision   Moved server sessions → stateless JWT.
### Why        Horizontal scaling; sessions were node-pinned.
### Tradeoffs  No instant revoke; added 5-min TTL + denylist.
### Open       Refresh-token rotation still TODO.
EOF
```
Supersede an earlier decision:
```bash
recall append --title auth-v2 --session abc --supersedes 97f80d49-1 \
  --body - <<'EOF'
### Decision   Switch JWT → opaque tokens behind a gateway.
EOF
```

## `recall index`
(Re)build the search index from Markdown. Incremental by content hash by default.

| Flag | Meaning |
|------|---------|
| `--full` | Reindex every file, ignoring hashes (use after changing model/`dim`). |

```bash
recall index            # only changed workstreams
recall index --full     # rebuild everything
```
Prints `Indexed N chunks across M changed workstream(s)`; notes if it fell back to
BM25-only.

## `recall search`
Hybrid BM25 + semantic retrieval, printed as citable context (or JSON).

| Flag | Default | Meaning |
|------|---------|---------|
| `query` | *(positional, required)* | The search text. |
| `--all` | off | Search across **all** workstreams (else current/auto-detected). |
| `-k <N>` | `config.top_k` (6) | Number of results. |
| `--json` | off | Emit structured JSON instead of formatted context. |
| `--workstream`, `--type` | auto | Restrict to a specific workstream. |

```bash
recall search "how did we handle token revocation?"
recall search "rate limiting pattern" --all -k 10
recall search "eval metric" --workstream research/rag-eval --json
```
Superseded entries are excluded by default.

## `recall recent`
Show the latest entries (orientation: "where did we leave off?").

| Flag | Default | Meaning |
|------|---------|---------|
| `-n <N>` | `10` | How many entries. |
| `--all` | off | Across all workstreams. |
| `--workstream`, `--type` | auto | Restrict to one workstream. |

```bash
recall recent -n 5
recall recent --all
```
Each line shows `[ts] workstream — title (status)`.

## `recall workstreams`
List known workstreams with entry counts.
```bash
recall workstreams
#    2  acme/api-gateway  (acme__api-gateway)
#    1  research/rag-eval  (research__rag-eval)
```

## `recall consolidate`
Distill each workstream's **active** entries into `<slug>.summary.md` (durable
Tier-1 memory) and write a `_index.md` catalog.
```bash
recall consolidate
# → Wrote 3 summary file(s).
```

## `recall doctor`
Diagnose configuration, paths, `sqlite-vec`, and Ollama reachability.
```bash
recall doctor
```
Use it first whenever search behaves unexpectedly.

---

## Exit codes & scripting
All commands return `0` on success. `--json` on `search` makes output easy to pipe:
```bash
recall search "retry policy" --all --json | jq '.[].chunk_id'
```
