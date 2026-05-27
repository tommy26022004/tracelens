"""Provider-agnostic embeddings interface.

Mirrors the shape of `app.core.llm`. Agent / ingestion code depends only
on `get_embeddings()` so the provider can swap without ripple.
"""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings


class EmbeddingsProvider(Protocol):
    """A minimal sync interface for embedding documents."""

    dimension: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class GeminiEmbeddings:
    """Google `gemini-embedding-001` via the `google-genai` SDK.

    The native model emits 3072-dim vectors; we request a truncated
    768-dim output so the Qdrant collection size stays compact and any
    swap with smaller open models (e.g. BGE) stays drop-in.

    Falls back to deterministic zero-cost stub vectors when no API key
    is configured, keeping unit tests offline-friendly.
    """

    dimension: int = 768
    model: str = "gemini-embedding-001"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.gemini_api_key
        self._client = None

    def _ensure_client(self):  # type: ignore[no-untyped-def]
        if self._client is None and self._api_key:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def _embed(self, text: str, task_type: str) -> list[float]:
        client = self._ensure_client()
        if client is None:
            # Deterministic stub: hash → bounded float vector. Lets tests run
            # without network access; production paths require a real key.
            import hashlib

            seed = int.from_bytes(
                hashlib.sha256(text.encode("utf-8")).digest()[:8], "big"
            )
            rng = _LCG(seed)
            return [rng.next_float() for _ in range(self.dimension)]

        from google.genai import types

        response = client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.dimension,
            ),
        )
        # SDK returns response.embeddings: list[ContentEmbedding]; one item per
        # input string. We pass a single string so we take element 0.
        return list(response.embeddings[0].values)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t, task_type="RETRIEVAL_DOCUMENT") for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, task_type="RETRIEVAL_QUERY")


class _LCG:
    """Tiny linear congruential RNG — deterministic stub vector source."""

    def __init__(self, seed: int) -> None:
        self._state = seed or 1

    def next_float(self) -> float:
        self._state = (self._state * 1103515245 + 12345) & 0x7FFFFFFF
        # map into [-1, 1)
        return (self._state / 0x40000000) - 1.0


def get_embeddings() -> EmbeddingsProvider:
    if settings.llm_provider == "gemini":
        return GeminiEmbeddings()
    raise ValueError(f"No embeddings adapter for provider: {settings.llm_provider}")
