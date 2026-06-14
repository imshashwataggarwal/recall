from recall.capture import EntryInput, append_entry, workstream_path
from recall.config import load_config
from recall.parser import chunks_from_file, parse_entries
from recall import workstream as ws_mod


def _setup(recall_home):
    cfg = load_config()
    w = ws_mod.resolve(label="acme/api-gateway", type_hint="repo")
    return cfg, w


def test_append_creates_header_and_entry(recall_home):
    cfg, w = _setup(recall_home)
    eid = append_entry(cfg, w, EntryInput(
        title="auth-refactor", body="### Decision   Use JWT.",
        session="abc123", tags=["auth", "jwt"]))
    assert eid == "abc123-1"
    text = workstream_path(cfg, w).read_text()
    assert "recall:workstream=acme/api-gateway type=repo" in text
    assert "recall:entry id=abc123-1" in text
    assert "tags=[auth,jwt]" in text
    assert "status=active" in text


def test_sequential_entry_ids(recall_home):
    cfg, w = _setup(recall_home)
    append_entry(cfg, w, EntryInput(title="a", body="x", session="s"))
    eid2 = append_entry(cfg, w, EntryInput(title="b", body="y", session="s"))
    assert eid2 == "s-2"


def test_supersede_flips_status(recall_home):
    cfg, w = _setup(recall_home)
    e1 = append_entry(cfg, w, EntryInput(title="old", body="### Decision Sessions.",
                                         session="s"))
    append_entry(cfg, w, EntryInput(title="new", body="### Decision JWT.",
                                    session="s", supersedes=[e1]))
    entries = parse_entries(workstream_path(cfg, w).read_text())
    by_id = {e.entry_id: e for e in entries}
    assert by_id[e1].status == "superseded"


def test_parser_chunks(recall_home):
    cfg, w = _setup(recall_home)
    append_entry(cfg, w, EntryInput(title="auth-refactor",
                                    body="### Decision   Use JWT.\n### Why   Scale.",
                                    session="s", tags=["auth"]))
    chunks = chunks_from_file(workstream_path(cfg, w))
    assert len(chunks) == 1
    c = chunks[0]
    assert c.chunk_id == "acme__api-gateway:s-1"
    assert "Workstream: acme/api-gateway" in c.text
    assert "Use JWT" in c.text
    assert c.tags == ["auth"]
