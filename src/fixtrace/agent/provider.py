"""Provider-neutral model interface and an OpenAI Responses API adapter."""

from __future__ import annotations

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fixtrace.core.config import Settings


class AgentModel(Protocol):
    provider: str
    model: str

    def complete(self, messages: list[dict[str, str]]) -> str: ...


class AgentModelError(RuntimeError):
    """Raised when an LLM provider cannot return a usable response."""


class OpenAIResponsesModel:
    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def complete(self, messages: list[dict[str, str]]) -> str:
        instructions = "\n\n".join(
            message["content"] for message in messages if message["role"] == "system"
        )
        transcript = json.dumps(
            [message for message in messages if message["role"] != "system"],
            ensure_ascii=False,
        )
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": "Continue this agent transcript encoded as JSON:\n" + transcript,
            "store": False,
            "max_output_tokens": 1600,
        }
        request = Request(
            self._endpoint(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise AgentModelError(
                f"OpenAI API request failed with HTTP {exc.code}."
            ) from exc
        except URLError as exc:
            raise AgentModelError(
                "OpenAI API request could not reach the configured endpoint."
            ) from exc
        except (TimeoutError, json.JSONDecodeError) as exc:
            raise AgentModelError("OpenAI API returned no usable response.") from exc

        text = result.get("output_text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        for item in result.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return str(content["text"]).strip()
        raise AgentModelError("OpenAI API response did not contain output text.")

    def _endpoint(self) -> str:
        if self.base_url.endswith("/responses"):
            return self.base_url
        return f"{self.base_url}/responses"


def build_agent_model(settings: Settings) -> AgentModel | None:
    if not settings.llm_configured:
        return None
    if settings.llm_provider == "openai":
        assert settings.llm_api_key is not None
        return OpenAIResponsesModel(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return None
