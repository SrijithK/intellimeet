from __future__ import annotations

import hashlib
from collections.abc import Sequence

from app.db_models import EMBEDDING_DIM


class FakeEmbedder:
    """Deterministic, model-free embedder for tests that don't care about semantics."""

    dim = EMBEDDING_DIM

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [digest[i % len(digest)] / 255.0 for i in range(self.dim)]


class FakeLLM:
    """Returns a canned JSON response (or raises) and records the prompts it was given."""

    name = "fake"

    def __init__(self, response=None, error=None):
        self.response = response if response is not None else {"decisions": [], "action_items": [], "topics": []}
        self.error = error
        self.calls = []

    def complete_json(self, system, user, schema):
        self.calls.append(user)
        if self.error is not None:
            raise self.error
        return self.response(user) if callable(self.response) else self.response
