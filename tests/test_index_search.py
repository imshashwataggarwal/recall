from recall.capture import EntryInput, append_entry, workstream_path
from recall.config import load_config
from recall.indexer import index_all, index_file
from recall.search import search
from recall.store import Store
from recall import workstream as ws_mod


def _seed(cfg, label, entries):
    w = ws_mod.resolve(label=label)
    for title, body, tags in entries:
        append_entry(cfg, w, EntryInput(title=title, body=body, session="s", tags=tags))
    return w


def test_index_and_bm25_search(recall_home, fake_embedder):
    cfg = load_config()
    _seed(cfg, "acme/api", [
        ("auth-refactor", "### Decision   Use stateless JWT for authentication.", ["auth"]),
        ("caching", "### Decision   Add Redis caching layer for hot reads.", ["cache"]),
    ])
    store = Store(cfg)
    res = index_all(cfg, store, fake_embedder)
    assert sum(res.values()) == 2

    hits = search(cfg, store, "JWT authentication", embedder=fake_embedder,
                  workstream="acme__api")
    store.close()
    assert hits
    assert "JWT" in hits[0].chunk.text


def test_incremental_reindex_skips_unchanged(recall_home, fake_embedder):
    cfg = load_config()
    w = _seed(cfg, "acme/api", [("a", "### Decision   Alpha.", [])])
    store = Store(cfg)
    index_all(cfg, store, fake_embedder)
    again = index_file(cfg, store, fake_embedder, workstream_path(cfg, w))
    store.close()
    assert again == {}  # unchanged → nothing reindexed


def test_superseded_excluded_by_default(recall_home, fake_embedder):
    cfg = load_config()
    w = ws_mod.resolve(label="acme/api")
    e1 = append_entry(cfg, w, EntryInput(title="old",
                      body="### Decision   Use server sessions for auth.",
                      session="s"))
    append_entry(cfg, w, EntryInput(title="new",
                 body="### Decision   Use server sessions JWT auth replacement.",
                 session="s", supersedes=[e1]))
    store = Store(cfg)
    index_all(cfg, store, fake_embedder)
    hits = search(cfg, store, "server sessions auth", embedder=fake_embedder,
                  workstream="acme__api", include_superseded=False)
    store.close()
    assert all(h.chunk.status == "active" for h in hits)


def test_cross_workstream_search(recall_home, fake_embedder):
    cfg = load_config()
    _seed(cfg, "repo/one", [("x", "### Decision   Use exponential backoff retries.", [])])
    _seed(cfg, "repo/two", [("y", "### Decision   Use exponential backoff for retries.", [])])
    store = Store(cfg)
    index_all(cfg, store, fake_embedder)
    scoped = search(cfg, store, "backoff retries", embedder=fake_embedder,
                    workstream="repo__one")
    crossed = search(cfg, store, "backoff retries", embedder=fake_embedder,
                     all_workstreams=True)
    store.close()
    assert {h.chunk.workstream_slug for h in scoped} == {"repo__one"}
    assert {h.chunk.workstream_slug for h in crossed} >= {"repo__one", "repo__two"}
