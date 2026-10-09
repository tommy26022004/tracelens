from types import SimpleNamespace

import pytest

from app.core.embeddings import GeminiEmbeddings, LocalHashEmbeddings


class FakeModels:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_content(self, *, model: str, contents: list[str], config: object) -> object:
        self.calls.append(contents)
        embeddings = [SimpleNamespace(values=[float(len(text))] * 3) for text in contents]
        return SimpleNamespace(embeddings=embeddings)


def test_embed_documents_batches_requests() -> None:
    provider = GeminiEmbeddings(api_key="test")
    provider.dimension = 3
    provider.batch_size = 2
    models = FakeModels()
    provider._client = SimpleNamespace(models=models)

    vectors = provider.embed_documents(["a", "bb", "ccc", "dddd", "eeeee"])

    assert [len(batch) for batch in models.calls] == [2, 2, 1]
    assert vectors == [
        [1.0, 1.0, 1.0],
        [2.0, 2.0, 2.0],
        [3.0, 3.0, 3.0],
        [4.0, 4.0, 4.0],
        [5.0, 5.0, 5.0],
    ]


def test_embed_query_uses_single_item_batch() -> None:
    provider = GeminiEmbeddings(api_key="test")
    provider.dimension = 3
    models = FakeModels()
    provider._client = SimpleNamespace(models=models)

    vector = provider.embed_query("query")

    assert models.calls == [["query"]]
    assert vector == [5.0, 5.0, 5.0]


def test_local_embeddings_are_normalized_and_lexical() -> None:
    provider = LocalHashEmbeddings()

    revenue = provider.embed_query("audited annual revenue")
    matching = provider.embed_query("annual revenue from audited accounts")
    unrelated = provider.embed_query("director identity registration")

    matching_score = sum(left * right for left, right in zip(revenue, matching, strict=True))
    unrelated_score = sum(left * right for left, right in zip(revenue, unrelated, strict=True))

    assert sum(value * value for value in revenue) == pytest.approx(1.0)
    assert matching_score > unrelated_score
