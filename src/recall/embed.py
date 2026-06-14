"""Ollama embedding client.

Talks to a local Ollama server's ``/api/embed`` endpoint. Designed to fail with
a clear, actionable error when Ollama isn't running, and to be trivially
mockable in tests (callers can inject any object with an ``embed`` method).
"""
from __future__ import annotations

import time
from typing import Sequence

import requests

from .config import Config


class EmbeddingError(RuntimeError):
    pass


class OllamaEmbedder:
    def __init__(self, host: str, model: str, dim: int,
                 timeout: float = 60.0, retries: int = 3) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.dim = dim
        self.timeout = timeout
        self.retries = retries

    @classmethod
    def from_config(cls, cfg: Config) -> "OllamaEmbedder":
        return cls(host=cfg.ollama_host, model=cfg.embed_model, dim=cfg.embed_dim)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text (batched)."""
        if not texts:
            return []
        url = f"{self.host}/api/embed"
        payload = {"model": self.model, "input": list(texts)}
        last_err: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                embeddings = data.get("embeddings")
                if not embeddings:
                    raise EmbeddingError(f"No embeddings returned by Ollama: {data}")
                return embeddings
            except requests.exceptions.ConnectionError as exc:
                last_err = exc
                break  # server down — retrying won't help
            except requests.exceptions.RequestException as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise EmbeddingError(
            f"Failed to get embeddings from Ollama at {self.host} "
            f"(model '{self.model}'). Is Ollama running and the model pulled "
            f"(`ollama pull {self.model}`)? Underlying error: {last_err}"
        )

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
