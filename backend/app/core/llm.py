"""Provider-agnostic LLM wrapper.

Two surfaces:
- `generate_text(prompt)` for free-form completions (rarely used; only
  the summary node needs it).
- `generate_structured(prompt, schema)` for any node that needs a
  reliably-parseable Pydantic object back. Each provider is asked for
  schema-constrained JSON and the result is validated locally.

Test code substitutes a fake provider via `set_default_provider()` so
agent unit tests can run fully offline.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from time import sleep
from typing import Any, Protocol, TypeVar

import httpx
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


class GroqLLM:
    """Groq chat completions through its OpenAI-compatible HTTP API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        self._api_key = api_key or settings.groq_api_key
        self._model = model or settings.groq_model
        self._base_url = (base_url or settings.groq_base_url).rstrip("/")
        self._client = client
        self._sleep = sleep_fn

    def _ensure_client(self) -> httpx.Client:
        if not self._api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not configured. "
                "Set it in backend/.env or use a fake provider in tests."
            )
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=120.0,
            )
        return self._client

    def _chat_completion(self, prompt: str, **options: Any) -> str:
        request = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            **options,
        }
        response: httpx.Response | None = None
        for attempt in range(4):
            response = self._ensure_client().post("/chat/completions", json=request)
            retryable_rate_limit = response.status_code == 429
            if response.status_code == 413:
                try:
                    detail = str(response.json().get("error", {}).get("message", "")).lower()
                except (AttributeError, ValueError):
                    detail = response.text.lower()
                retryable_rate_limit = "tokens per minute" in detail or "tpm" in detail
            if not retryable_rate_limit or attempt == 3:
                break
            retry_after = response.headers.get("retry-after")
            try:
                delay = (
                    float(retry_after)
                    if retry_after is not None
                    else 30.0
                    if response.status_code == 413
                    else 2 ** (attempt + 1)
                )
            except ValueError:
                delay = 2 ** (attempt + 1)
            self._sleep(min(max(delay, 0.0), 60.0))
        if response is None:
            raise RuntimeError("Groq request was not attempted.")
        if response.is_error:
            try:
                error_payload = response.json().get("error", {})
                detail = error_payload.get("message") or error_payload.get("code")
            except (AttributeError, ValueError):
                detail = response.text
            message = str(detail or response.reason_phrase).splitlines()[0][:500]
            raise RuntimeError(f"Groq API error {response.status_code}: {message}")
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Groq returned an invalid chat completion response.") from exc
        if not isinstance(content, str):
            raise RuntimeError("Groq returned a chat completion without text content.")
        return content

    def generate_text(self, prompt: str) -> str:
        return self._chat_completion(prompt)

    def generate_structured(self, prompt: str, schema: type[T]) -> T:
        schema_json = json.dumps(schema.model_json_schema(), separators=(",", ":"))
        content = self._chat_completion(
            prompt
            + "\n\nReturn only one valid JSON object matching this schema exactly. "
            + "Do not use Markdown fences or comments. Escape every line break inside "
            + "a JSON string as \\n; never place a literal newline inside a string value.\n"
            + schema_json,
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        return schema.model_validate_json(content)


_default_provider: LLMProvider | None = None


def get_llm() -> LLMProvider:
    """Return the configured provider. Tests can override via
    `set_default_provider()`."""
    global _default_provider
    if _default_provider is not None:
        return _default_provider
    if settings.llm_provider == "gemini":
        return GeminiLLM()
    if settings.llm_provider == "groq":
        return GroqLLM()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def set_default_provider(provider: LLMProvider | None) -> None:
    """Install a process-wide default provider. Pass `None` to reset."""
    global _default_provider
    _default_provider = provider
