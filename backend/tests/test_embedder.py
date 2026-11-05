import numpy as np
import pytest

from app.db_models import EMBEDDING_DIM
from app.services.embedder import FastEmbedEmbedder


@pytest.fixture(scope="module")
def embedder():
    # Real model (downloaded once to the fastembed cache, ~130MB).
    return FastEmbedEmbedder()


def test_embeds_documents_with_schema_dimension(embedder):
    vectors = embedder.embed_documents(["We decided to postpone the launch.", "Bob owns the checklist."])

    assert len(vectors) == 2
    assert all(len(vector) == EMBEDDING_DIM for vector in vectors)


def test_related_text_is_closer_than_unrelated_text(embedder):
    query = np.array(embedder.embed_query("When is the launch happening?"))
    related, unrelated = (
        np.array(v)
        for v in embedder.embed_documents(
            ["We agreed to move the product launch to next quarter.", "The office coffee machine is broken."]
        )
    )

    assert query @ related > query @ unrelated


def test_empty_input_returns_empty_list(embedder):
    assert embedder.embed_documents([]) == []


def test_unknown_model_raises_instead_of_falling_back():
    with pytest.raises(ValueError):
        FastEmbedEmbedder(model_name="not-a-real/model").embed_documents(["hello"])
