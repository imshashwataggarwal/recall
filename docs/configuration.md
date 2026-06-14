# Configuration

Recall reads `~/.recall/config.toml`. Every key has a sensible default, so the
file is optional — `recall init` writes a starter version.

## Location & override

- Default home: `~/.recall/`
- Override with the **`RECALL_HOME`** environment variable. This relocates the
  *entire* KB (config, sessions, index, logs) and is how the test-suite isolates
  state:
  ```bash
  RECALL_HOME=/tmp/recall-sandbox recall doctor
  ```

## `config.toml` reference

```toml
# ~/.recall/config.toml

[ollama]
host = "http://localhost:11434"   # where your local Ollama server listens

[embedding]
model = "embeddinggemma"          # any Ollama embedding model
dim   = 768                       # MUST match the model's output dimension

[search]
top_k = 6                         # default number of results
rrf_k = 60                        # Reciprocal Rank Fusion constant (higher = flatter)
recency_half_life_days = 45.0     # days for a result's recency weight to halve
```

### Key-by-key

| Section | Key | Default | Effect |
|---------|-----|---------|--------|
| `ollama` | `host` | `http://localhost:11434` | Ollama server URL used for embeddings. |
| `embedding` | `model` | `embeddinggemma` | Embedding model name (`ollama pull <model>`). |
| `embedding` | `dim` | `768` | Vector dimension. **Must equal the model's real dim** or the vec table won't match. Change it → run `recall index --full`. |
| `search` | `top_k` | `6` | Default `-k` for `recall search` / `mem_search`. |
| `search` | `rrf_k` | `60` | RRF damping. Lower → top ranks dominate; higher → flatter fusion. |
| `search` | `recency_half_life_days` | `45.0` | Smaller → newer entries win harder; larger → recency matters less. |

## Choosing / changing the embedding model

1. Pull it: `ollama pull <model>` (e.g. `nomic-embed-text`, `mxbai-embed-large`).
2. Set `embedding.model` and the matching `embedding.dim` in `config.toml`.
3. Rebuild vectors: `recall index --full` (dimension changes invalidate old vectors).

> Tip: run `recall doctor` afterwards to confirm Ollama is reachable with the new
> model.

## Tuning retrieval

- **Too much old noise?** Lower `recency_half_life_days` (e.g. `21`).
- **Want pure relevance, ignore age?** Raise it (e.g. `365`).
- **Results too narrow?** Raise `top_k`, or search with `--all` for cross-workstream.
- **One retriever dominating?** Adjust `rrf_k`; it's the `k` in `1/(k+rank)`.

The recency blend itself (`0.6*relevance + 0.4*recency`) lives in
`src/recall/search.py` if you want to change the relevance/recency balance.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `RECALL_HOME` | Relocate the whole knowledge base (config + data + index + logs). |

That's the only environment variable Recall reads. Everything else is config or
CLI flags.
