from __future__ import annotations

import hashlib


class LocalEmbedder:
    def __init__(self, model_name: str = "bge-small-en", embedding_dim: int = 8) -> None:
        self.model_name = model_name
        self.embedding_dim = embedding_dim

    def embed_text(self, text: str) -> list[float]:
        try:
            from fastembed import TextEmbedding

            embedding = TextEmbedding(model_name=self.model_name)
            result = embedding.embed([text])[0]
            return [float(value) for value in result]
        except Exception:
            return self._fallback_embedding(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]

    def _fallback_embedding(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.lower().encode("utf-8")).digest()
        vector: list[float] = []
        for index in range(self.embedding_dim):
            value = (digest[index % len(digest)] + index * 17) % 101
            vector.append(round(value / 100.0, 6))
        return vector
