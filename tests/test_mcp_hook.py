import json
import subprocess
import sys
from pathlib import Path

from recall.config import load_config
from recall.indexer import index_all
from recall.store import Store
from recall import mcp_server, workstream as ws_mod
from recall.capture import EntryInput, append_entry


def test_mcp_tools_roundtrip(recall_home, monkeypatch):
    # Force BM25-only path (no Ollama) by disabling the embedder.
    monkeypatch.setattr(mcp_server, "_embedder", lambda cfg, store: None)

    res = mcp_server.mem_append(title="auth", body="### Decision   Use JWT tokens.",
                                workstream="acme/api", session="s", tags=["auth"])
    assert res["entry_id"] == "s-1"

    ws = mcp_server.mem_workstreams()
    assert any(w["name"] == "acme/api" for w in ws)

    ctx = mcp_server.mem_search("JWT tokens", workstream="acme/api")
    assert "JWT" in ctx

    recent = mcp_server.mem_recent(workstream="acme/api", n=5)
    assert recent and recent[0]["title"] == "auth"

    idx = mcp_server.mem_index(changed_only=False)
    assert isinstance(idx, dict)


def test_hook_captures_delta(recall_home):
    repo_root = Path(__file__).resolve().parents[1]
    hook = repo_root / "integrations" / "hooks" / "session_end.py"
    payload = json.dumps({
        "session": "h1", "workstream": "ops/oncall",
        "title": "incident", "summary": "### Note   Disk filled; added alert.",
        "tags": ["incident"],
    })
    env = {"RECALL_HOME": str(recall_home),
           "PYTHONPATH": str(repo_root / "src")}
    import os
    env = {**os.environ, **env}
    out = subprocess.run([sys.executable, str(hook), payload],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0

    cfg = load_config()
    w = ws_mod.resolve(label="ops/oncall")
    store = Store(cfg)
    index_all(cfg, store, None)
    recent = store.recent(w.slug, 5)
    store.close()
    assert any(c.title == "incident" for c in recent)


def test_hook_silent_on_bad_payload(recall_home):
    repo_root = Path(__file__).resolve().parents[1]
    hook = repo_root / "integrations" / "hooks" / "session_end.py"
    import os
    env = {**os.environ, "RECALL_HOME": str(recall_home),
           "PYTHONPATH": str(repo_root / "src")}
    out = subprocess.run([sys.executable, str(hook), "not-json{"],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0  # never fails the shutdown
