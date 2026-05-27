"""Provider-agnostic LLM wrapper.

The agent only depends on this interface. Swap Gemini for Bedrock / OpenAI / Ollama
without touching agent code.
"""

from __future__ import annotations

from typing import Protocol

from langchain_core.language_models import BaseChatModel

from app.core.config import settings


class LLMProvider(Protocol):
    def chat_model(self) -> BaseChatModel: ...


class GeminiProvider:
    def chat_model(self) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0,
        )


def get_llm() -> BaseChatModel:
    if settings.llm_provider == "gemini":
        return GeminiProvider().chat_model()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
