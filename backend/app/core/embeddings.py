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
    """Google `text-embedding-004` — free tier, 768-dim.

    Uses `google-generativeai` directly (no LangChain dependency) so this
    module stays usable from ingestion code that doesn't otherwise need
    LangChain. Falls back to deterministic zero-vectors when no API key
    is configured, which keeps unit tests offline-friendly.
    """

    dimension: int = 768
    model: str = "models/text-embedding-004"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.gemini_api_key

    def _embed(self, text: str, task_type: str) -> list[float]:
        if not self._api_key:
            # Deterministic stub: hash → bounded float vector. Lets tests run
            # without network access; production paths require a real key.
            import hashlib

            seed = int.from_bytes(
                hashlib.sha256(text.encode("utf-8")).digest()[:8], "big"
            )
            rng = _LCG(seed)
            return [rng.next_float() for _ in range(self.dimension)]

        import google.generativeai as genai

        genai.configure(api_key=self._api_key)
        response = genai.embed_content(model=self.model, content=text, task_type=task_type)
        return list(response["embedding"])

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
