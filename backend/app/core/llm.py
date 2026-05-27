"""Provider-agnostic LLM wrapper.

Two surfaces:
- `generate_text(prompt)` for free-form completions (rarely used; only
  the summary node needs it).
- `generate_structured(prompt, schema)` for any node that needs a
  reliably-parseable Pydantic object back. Uses Gemini's native
  `response_schema` so we don't have to write JSON repair logic.

Test code substitutes a fake provider via `set_default_provider()` so
agent unit tests can run fully offline.
"""

from __future__ import annotations

import json
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.core.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    def generate_text(self, prompt: str) -> str: ...

    def generate_structured(self, prompt: str, schema: type[T]) -> T: ...


class GeminiLLM:
    """gemini-2.5-flash by default. Configured via `settings.gemini_model`."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or settings.gemini_api_key
        self._model = model or settings.gemini_model
        self._client = None

    def _ensure_client(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY is not configured. "
                    "Set it in backend/.env or use a fake provider in tests."
                )
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def generate_text(self, prompt: str) -> str:
        client = self._ensure_client()
        response = client.models.generate_content(model=self._model, contents=prompt)
        return response.text or ""

    def generate_structured(self, prompt: str, schema: type[T]) -> T:
        client = self._ensure_client()
        from google.genai import types

        response = client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        # SDK exposes the parsed object directly when response_schema is set,
        # but we fall back to JSON loading for resilience across SDK versions.
        if getattr(response, "parsed", None) is not None:
            return response.parsed  # type: ignore[return-value]
        return schema.model_validate_json(response.text or "{}")


_default_provider: LLMProvider | None = None


def get_llm() -> LLMProvider:
    """Return the configured provider. Tests can override via
    `set_default_provider()`."""
    global _default_provider
    if _default_provider is not None:
        return _default_provider
    if settings.llm_provider == "gemini":
        return GeminiLLM()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def set_default_provider(provider: LLMProvider | None) -> None:
    """Install a process-wide default provider. Pass `None` to reset."""
    global _default_provider
    _default_provider = provider
