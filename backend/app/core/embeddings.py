"""Provider-agnostic embeddings interface.

Mirrors the shape of `app.core.llm`. Agent / ingestion code depends only
on `get_embeddings()` so the provider can swap without ripple.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.config import settings


class EmbeddingsProvider(Protocol):
    """A minimal sync interface for embedding documents."""

    dimension: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class LocalHashEmbeddings:
    """Zero-cost lexical feature hashing for local Qdrant retrieval."""

    dimension: int = 768

    @property
    def space_id(self) -> str:
        return f"local-hash-v1:{self.dimension}"

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude:
            return [value / magnitude for value in vector]
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


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
    batch_size: int = 64

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.gemini_api_key
        self._client = None

    def _ensure_client(self):  # type: ignore[no-untyped-def]
        if self._client is None and self._api_key:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    @property
    def space_id(self) -> str:
        mode = "gemini" if self._api_key else "stub"
        return f"{mode}:{self.model}:{self.dimension}"

    @retry(
        retry=retry_if_exception(lambda exc: _is_retryable_embedding_error(exc)),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(6),
        reraise=True,
    )
    def _embed_batch(self, texts: list[str], task_type: str) -> list[list[float]]:
        if not texts:
            return []
        client = self._ensure_client()
        if client is None:
            return [_stub_vector(text, self.dimension) for text in texts]

        from google.genai import types

        response = client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.dimension,
            ),
        )
        return [list(embedding.values) for embedding in response.embeddings]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(
                self._embed_batch(
                    texts[start : start + self.batch_size],
                    task_type="RETRIEVAL_DOCUMENT",
                )
            )
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batch([text], task_type="RETRIEVAL_QUERY")[0]


def _is_retryable_embedding_error(exc: BaseException) -> bool:
    message = str(exc).upper()
    return any(
        marker in message
        for marker in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "DEADLINE_EXCEEDED")
    )


def _stub_vector(text: str, dimension: int) -> list[float]:
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = _LCG(seed)
    return [rng.next_float() for _ in range(dimension)]


class _LCG:
    """Tiny linear congruential RNG — deterministic stub vector source."""

    def __init__(self, seed: int) -> None:
        self._state = seed or 1

    def next_float(self) -> float:
        self._state = (self._state * 1103515245 + 12345) & 0x7FFFFFFF
        # map into [-1, 1)
        return (self._state / 0x40000000) - 1.0


def get_embeddings() -> EmbeddingsProvider:
    if settings.embeddings_provider == "local":
        return LocalHashEmbeddings()
    if settings.embeddings_provider == "gemini":
        return GeminiEmbeddings()
    raise ValueError(f"No embeddings adapter for provider: {settings.embeddings_provider}")
