from recall import workstream as ws


def test_slugify_roundtrip():
    assert ws.slugify("acme/api-gateway") == "acme__api-gateway"
    assert ws.unslugify("acme__api-gateway") == "acme/api-gateway"


def test_slugify_sanitizes():
    assert ws.slugify("Research: RAG Eval!!") == "research-rag-eval"
    assert ws.slugify("") == "default"


def test_resolve_explicit_label():
    w = ws.resolve(label="research/rag-eval")
    assert w.name == "research/rag-eval"
    assert w.slug == "research__rag-eval"
    assert w.type == "manual"


def test_resolve_type_hint():
    w = ws.resolve(label="ops/oncall", type_hint="ops")
    assert w.type == "ops"


def test_resolve_no_git_raises(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        ws.resolve(cwd=tmp_path)
