"""Shared pytest fixtures: isolated RECALL_HOME + a deterministic fake embedder."""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture()
def recall_home(tmp_path, monkeypatch):
    home = tmp_path / ".recall"
    monkeypatch.setenv("RECALL_HOME", str(home))
    return home


class FakeEmbedder:
    """Deterministic hash-based embeddings — no Ollama needed in tests."""
    def __init__(self, dim: int = 768):
        self.dim = dim

    def embed(self, texts):
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            # Tile the 32-byte digest into a dim-length unit-ish vector.
            vec = [((h[i % len(h)] / 255.0) - 0.5) for i in range(self.dim)]
            out.append(vec)
        return out


@pytest.fixture()
def fake_embedder():
    return FakeEmbedder()
