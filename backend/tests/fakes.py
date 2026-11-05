from __future__ import annotations

import hashlib
from typing import List, Sequence

from app.db_models import EMBEDDING_DIM


class FakeEmbedder:
    """Deterministic, model-free embedder for tests that don't care about semantics."""

    dim = EMBEDDING_DIM

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._vector(text)

    def _vector(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [digest[i % len(digest)] / 255.0 for i in range(self.dim)]
