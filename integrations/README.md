# Integrations

Drop-in assets that wire Recall into Copilot CLI (and other agentic CLIs). The
core tool (`recall`, `recall-mcp`) works without any of these — they just make
read/write automatic instead of manual.

| Asset | What it does | How to use |
| --- | --- | --- |
| [`copilot-instructions.snippet.md`](copilot-instructions.snippet.md) | Tells the agent *when* to search memory and *when* to write it. | Paste into your repo's `.github/copilot-instructions.md` (or `AGENTS.md`). |
| [`skills/mem-summarize/SKILL.md`](skills/mem-summarize/SKILL.md) | A `/mem-summarize` skill that distills a session into a durable summary. | Copy the `mem-summarize/` folder into your agent's skills directory. |
| [`hooks/session_end.py`](hooks/session_end.py) | Fail-safe session-end hook that captures the session delta automatically. Never blocks shutdown. | Register as a Copilot session-end hook (see below). |

## Session-end hook

```bash
python integrations/hooks/session_end.py   # reads a JSON session payload on stdin
```

The hook is defensive by design: malformed input or an unavailable index exits
`0` so it can never fail a shutdown. See
[`../docs/mcp-and-copilot.md`](../docs/mcp-and-copilot.md) and
[`../docs/call-flows.md`](../docs/call-flows.md) for the full wiring and flow.
