# Call flows

End-to-end sequence diagrams for each operation. File references point at
`src/recall/*` unless noted.

## 1. Capture — `recall append` (and `mem_append`)

```mermaid
sequenceDiagram
    participant U as User / Agent
    participant CLI as cli.cmd_append
    participant WS as workstream.resolve
    participant CAP as capture.append_entry
    participant FS as ~/.recall/sessions/<slug>.md
    participant IDX as indexer.index_file

    U->>CLI: recall append --title T --session S --body -
    CLI->>WS: resolve(label?) → owner/repo or label
    WS-->>CLI: Workstream(name, slug, type)
    CLI->>CAP: append_entry(cfg, ws, EntryInput)
    CAP->>FS: read existing text (or "")
    CAP->>CAP: ensure header, compute next entry id
    alt entry supersedes older ids
        CAP->>FS: flip matching entries status=active→superseded
    end
    CAP->>FS: write header + existing + new entry block
    CAP-->>CLI: entry_id
    opt not --no-index
        CLI->>IDX: index_file(changed file)
    end
    CLI-->>U: "Appended <id> to <path>"
```

Key points: entry ids are `"{session}-{n}"` (sequential per session); the writer
is append-only; supersession edits old entries' status in place but never deletes.

## 2. Index — `recall index`

```mermaid
sequenceDiagram
    participant CLI as cli.cmd_index
    participant ST as store.Store
    participant IDX as indexer.index_all
    participant PAR as parser.chunks_from_file
    participant EMB as embed.OllamaEmbedder
    participant DB as recall.db

    CLI->>ST: open Store (loads sqlite-vec if available)
    CLI->>IDX: index_all(changed_only)
    loop each sessions/*.md (skip _*, *.summary.md)
        IDX->>DB: stored_hash(slug)
        IDX->>IDX: new_hash = sha256(file)
        alt changed_only and hash unchanged
            IDX-->>IDX: skip
        else
            IDX->>PAR: chunks_from_file(path)
            alt sqlite-vec enabled
                IDX->>EMB: embed([chunk.text ...])
                EMB-->>IDX: vectors (or exception → None)
            end
            IDX->>DB: upsert_workstream(slug, chunks, vectors, hash)
        end
    end
    IDX-->>CLI: {slug: n_chunks}
```

If embedding raises (Ollama down), `_embed_chunks` catches it and returns `None`,
so the chunk is still indexed for BM25 — indexing never fails on a model outage.

## 3. Search — `recall search` (and `mem_search`)

```mermaid
sequenceDiagram
    participant U as User / Agent
    participant SR as search.search
    participant ST as store.Store
    participant EMB as embed.OllamaEmbedder

    U->>SR: search(query, workstream?, all?, k)
    SR->>ST: bm25(OR-tokenized query, pool)
    ST-->>SR: ranked BM25 hits
    opt embedder present & vec enabled
        SR->>EMB: embed([query])
        EMB-->>SR: query vector
        SR->>ST: knn(qvec, pool)
        ST-->>SR: ranked semantic hits
    end
    SR->>SR: RRF fuse both lists (1/(rrf_k+rank))
    SR->>SR: drop superseded, filter by workstream
    SR->>SR: blend recency: score*(0.6+0.4*decay(ts))
    SR->>SR: sort desc, take top-k
    SR-->>U: SearchHit[] → format_context() citable text
```

## 4. Consolidate — `recall consolidate`

```mermaid
sequenceDiagram
    participant CLI as cli.cmd_consolidate
    participant CON as consolidate.consolidate
    participant PAR as parser.chunks_from_file
    participant FS as ~/.recall/sessions/

    CLI->>CON: consolidate(cfg)
    loop each workstream *.md (skip _*, *.summary.md)
        CON->>PAR: chunks_from_file(path)
        CON->>CON: keep status==active chunks
        CON->>FS: write <slug>.summary.md (durable, Tier-1)
    end
    CON->>FS: write _index.md (catalog of all workstreams)
    CON-->>CLI: {slug: n_active}
```

## 5. MCP server — `recall-mcp`

```mermaid
sequenceDiagram
    participant Host as Copilot / MCP host
    participant MCP as recall-mcp (FastMCP stdio)
    participant Fns as mem_* functions
    participant Core as capture / indexer / search / store

    Host->>MCP: launch (command: "recall-mcp")
    MCP->>MCP: register mem_search, mem_recent, mem_append,<br/>mem_workstreams, mem_index
    Host->>MCP: tool call (e.g. mem_search{query, workstream?})
    MCP->>Fns: mem_search(...)
    Fns->>Core: search(...) / append_entry(...) / ...
    Core-->>Fns: results
    Fns-->>Host: citable text / JSON
```

The `mem_*` functions are plain Python (unit-tested without an MCP runtime);
`main()` only wires them into a FastMCP stdio server.

## 6. Session-end hook — `integrations/hooks/session_end.py`

```mermaid
sequenceDiagram
    participant Copilot as Copilot CLI (session close)
    participant Hook as session_end.py
    participant Core as capture + indexer
    participant Log as ~/.recall/logs/hook.log

    Copilot->>Hook: run with JSON payload (argv[1] or stdin)
    Hook->>Hook: parse payload (session, workstream?, summary?, tags?)
    alt cwd provided
        Hook->>Hook: chdir(cwd) for git auto-detect
    end
    Hook->>Core: append_entry(final delta) + index_file
    alt any error
        Hook->>Log: append traceback
    end
    Hook-->>Copilot: exit 0 (always — never blocks shutdown)
```

The hook is deliberately **fail-safe**: bad payloads, missing workstream, or any
exception are logged and swallowed; it always exits `0` so it can never wedge a
session from closing.
