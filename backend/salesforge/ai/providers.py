"""LLM providers behind one interface. Both return the parsed JSON object the model produced."""

from __future__ import annotations

import json
from typing import Protocol

import httpx

from ..settings import Settings
from .schema import JSON_SCHEMA


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    model: str

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, object]: ...


def _parse(content: str) -> dict[str, object]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"model did not return JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ProviderError("model returned JSON that is not an object")
    return data


class OpenAICompatibleProvider:
    """Any /chat/completions API: Groq (free tier), OpenAI, Together, a local vLLM."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = client or httpx.Client(timeout=timeout, headers={"Authorization": f"Bearer {api_key}"})

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, object]:
        try:
            response = self._client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise ProviderError(f"LLM request failed: {type(exc).__name__}") from exc
        return _parse(content)


class OllamaProvider:
    """Local models via Ollama, with the JSON schema enforced by Ollama's structured output."""

    def __init__(self, base_url: str, model: str, timeout: float, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = client or httpx.Client(timeout=timeout)

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, object]:
        try:
            response = self._client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "format": JSON_SCHEMA,
                    "options": {"temperature": 0.2},
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ProviderError(f"LLM request failed: {type(exc).__name__}") from exc
        return _parse(content)


def build_provider(settings: Settings) -> Provider | None:
    if settings.llm_provider == "openai_compatible" and settings.llm_api_key:
        return OpenAICompatibleProvider(
            settings.llm_base_url, settings.llm_api_key, settings.llm_model, settings.llm_timeout_seconds
        )
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings.llm_base_url, settings.llm_model, settings.llm_timeout_seconds)
    return None
