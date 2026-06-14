"""Configuration loading for Recall.

Config lives at ``~/.recall/config.toml``. Sensible defaults are used when the
file (or any individual key) is missing, so Recall works out-of-the-box.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover - exercised on <3.11
    import tomli as _toml  # type: ignore


def _home() -> Path:
    """Root of the knowledge base. Override with ``RECALL_HOME`` (used by tests)."""
    return Path(os.environ.get("RECALL_HOME", str(Path.home() / ".recall")))


@dataclass
class Config:
    home: Path
    ollama_host: str = "http://localhost:11434"
    embed_model: str = "embeddinggemma"
    embed_dim: int = 768
    top_k: int = 6
    rrf_k: int = 60
    recency_half_life_days: float = 45.0

    # Derived paths
    sessions_dir: Path = field(init=False)
    index_dir: Path = field(init=False)
    db_path: Path = field(init=False)
    logs_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.sessions_dir = self.home / "sessions"
        self.index_dir = self.home / "index"
        self.db_path = self.index_dir / "recall.db"
        self.logs_dir = self.home / "logs"

    def ensure_dirs(self) -> None:
        for d in (self.home, self.sessions_dir, self.index_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


def load_config(home: Path | None = None) -> Config:
    home = home or _home()
    data: dict[str, Any] = {}
    cfg_path = home / "config.toml"
    if cfg_path.is_file():
        with cfg_path.open("rb") as fh:
            data = _toml.load(fh)

    ollama = data.get("ollama", {})
    embed = data.get("embedding", {})
    search = data.get("search", {})

    cfg = Config(
        home=home,
        ollama_host=ollama.get("host", "http://localhost:11434"),
        embed_model=embed.get("model", "embeddinggemma"),
        embed_dim=int(embed.get("dim", 768)),
        top_k=int(search.get("top_k", 6)),
        rrf_k=int(search.get("rrf_k", 60)),
        recency_half_life_days=float(search.get("recency_half_life_days", 45.0)),
    )
    return cfg


DEFAULT_CONFIG_TOML = """\
# Recall configuration (~/.recall/config.toml)

[ollama]
host = "http://localhost:11434"

[embedding]
model = "embeddinggemma"
dim = 768

[search]
top_k = 6
rrf_k = 60
recency_half_life_days = 45.0
"""
