from __future__ import annotations

import threading
from typing import List, Optional, Protocol, Sequence

from app.db_models import EMBEDDING_DIM

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class Embedder(Protocol):
    """Turns text into vectors. Swappable (e.g. Bedrock) via configuration."""

    dim: int

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]: ...

    def embed_query(self, text: str) -> List[float]: ...


class FastEmbedEmbedder:
    """Local ONNX embeddings via fastembed. The model is loaded once, on first use.

    Failures (missing package, download error) are raised, never papered over:
    a silent fallback would store vectors that make semantic search meaningless.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, batch_size: int = 64) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.dim = EMBEDDING_DIM
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from fastembed import TextEmbedding

                    self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        vectors = self._get_model().embed(list(texts), batch_size=self.batch_size)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> List[float]:
        return next(iter(self._get_model().query_embed(text))).tolist()


_default_embedder: Optional[FastEmbedEmbedder] = None


def get_embedder() -> Embedder:
    global _default_embedder
    if _default_embedder is None:
        _default_embedder = FastEmbedEmbedder()
    return _default_embedder
