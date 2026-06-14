---
name: mem-summarize
description: >-
  Distill the key decisions, tradeoffs, gotchas, and open threads from the
  current Copilot session so far into Recall (the personal knowledge base).
  Invoke periodically at meaningful milestones, or when the user runs
  /mem-summarize. Appends only the delta since the last summary.
---

# /mem-summarize — capture session knowledge into Recall

You are updating the user's **personal evolving knowledge base** (Recall). Your job
is to extract durable, reusable knowledge from the conversation so far and append it
as a single atomic entry to the correct workstream file.

## When to run
- The user explicitly invokes `/mem-summarize`.
- You (the agent) reach a meaningful milestone: a non-trivial decision was made, a
  tricky bug was understood, an approach was chosen/rejected, or scope changed.
- Avoid noise: only capture things worth remembering next session. Skip if nothing
  substantive happened since the last summary.

## What to capture (the delta only)
Summarize **only what is new since the last entry** in this session. Produce a tight,
structured block using these sections (omit any that don't apply):

```
### Decision   <what was decided>
### Why        <the reasoning / forces>
### Tradeoffs  <what we gave up; alternatives rejected>
### Gotchas    <surprises, footguns, environment quirks>
### Open       <unresolved threads / TODO for next time>
### Refs       <files, PRs, links>
```

Be concrete and self-contained — a future session must understand it without this chat.

## How to write it

1. **Resolve the workstream.**
   - If working in a git repo, let Recall auto-detect it (omit `--workstream`).
   - Otherwise pass an explicit label, e.g. `--workstream "research/rag-eval"`.

2. **Choose tags** (lowercase, comma-separated) and note any entry ids this
   **supersedes** (if this decision replaces an earlier one).

3. **Append via the MCP tool** (preferred) or the CLI:

   - MCP: call `mem_append` with `title`, `body` (the structured block above),
     `session` (the short session id), `tags`, and optional `supersedes`.
   - CLI fallback:
     ```bash
     recall append --title "auth-refactor" --session 97f80d49 \
       --tags auth,jwt,breaking --body - <<'EOF'
     ### Decision   Moved server sessions → stateless JWT.
     ### Why        Horizontal scaling; sessions were node-pinned.
     ### Tradeoffs  No instant revoke; added 5-min TTL + denylist.
     ### Open       Refresh-token rotation still TODO.
     EOF
     ```

4. Recall reindexes automatically after append. Confirm to the user with the
   returned entry id and the workstream name. Keep your chat reply to one line.

## Idempotency
Track what you've already summarized this session. On re-invocation, only append
new material — never restate prior entries.
