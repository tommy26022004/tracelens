import json

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.llm import GroqLLM, get_llm, set_default_provider
from app.explainability.summary import extract_citations


class ExampleResult(BaseModel):
    answer: str


def test_groq_generate_text_uses_chat_completions() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hello"}}]},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.groq.com/openai/v1",
        headers={"Authorization": "Bearer test-key"},
    )
    provider = GroqLLM(api_key="test-key", model="test-model", client=client)

    assert provider.generate_text("Hi") == "hello"
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"] == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Hi"}],
        "temperature": 0.1,
    }


def test_groq_generate_structured_validates_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"yes"}'}}]},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.groq.com/openai/v1",
    )
    provider = GroqLLM(api_key="test-key", model="test-model", client=client)

    assert provider.generate_structured("Question", ExampleResult) == ExampleResult(answer="yes")
    body = captured["body"]
    assert isinstance(body, dict)
    response_format = body["response_format"]
    assert response_format == {"type": "json_object"}
    assert body["temperature"] == 0.0
    assert '"answer"' in body["messages"][0]["content"]


def test_groq_retries_rate_limit_using_retry_after() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "recovered"}}]},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.groq.com/openai/v1",
    )
    provider = GroqLLM(
        api_key="test-key",
        model="test-model",
        client=client,
        sleep_fn=delays.append,
    )

    assert provider.generate_text("Hi") == "recovered"
    assert attempts == 2
    assert delays == [0.0]


def test_groq_retries_tpm_request_limit() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 4:
            return httpx.Response(
                413,
                json={"error": {"message": "Limit exceeded on tokens per minute (TPM)"}},
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "recovered"}}]},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.groq.com/openai/v1",
    )
    provider = GroqLLM(
        api_key="test-key",
        model="test-model",
        client=client,
        sleep_fn=delays.append,
    )

    assert provider.generate_text("Hi") == "recovered"
    assert attempts == 4
    assert delays == [30.0, 30.0, 30.0]


def test_get_llm_selects_groq(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    set_default_provider(None)
    monkeypatch.setattr(settings, "llm_provider", "groq")

    assert isinstance(get_llm(), GroqLLM)

    set_default_provider(None)


def test_severity_labels_are_not_treated_as_citations() -> None:
    text = "WARNING: missing evidence [WARNING] [doc-1:summary:0]"

    assert extract_citations(text) == ["doc-1:summary:0"]
