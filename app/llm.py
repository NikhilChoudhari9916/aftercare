from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from app.config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base class. Messages never contain prompts or patient text."""


class LLMUnavailable(LLMError):
    """Not configured, unreachable, timed out, or rate limited."""


class LLMRefused(LLMError):
    """The model declined the request (a safety classifier stop)."""


class LLMOutputError(LLMError):
    """The reply was cut off or could not be read as the requested shape."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    stop_reason: str
    # The raw content blocks, sent back unchanged as the assistant turn of the next request.
    content: list[Any]
    # What the call used, so a run can be costed and capped. Thinking counts as output.
    input_tokens: int = 0
    output_tokens: int = 0


class LLM(Protocol):
    """What the rest of the app needs from a language model. Tests replace it with a fake."""

    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        effort: str | None = None,
    ) -> LLMResponse: ...

    def extract(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 8192,
        effort: str | None = None,
    ) -> T: ...


class AnthropicLLM:
    """The only place in the app that talks to the Anthropic SDK."""

    def __init__(
        self, api_key: str, timeout: float, client: anthropic.Anthropic | None = None
    ) -> None:
        self._client = client or anthropic.Anthropic(
            api_key=api_key, timeout=timeout, max_retries=2
        )

    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        effort: str | None = None,
    ) -> LLMResponse:
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            params["tools"] = tools
        if effort:
            params["output_config"] = {"effort": effort}

        response = _call(self._client.messages.create, **params)
        _check_stop(response.stop_reason)
        text = "".join(block.text for block in response.content if block.type == "text")
        tool_calls = [
            ToolCall(id=block.id, name=block.name, input=dict(block.input))
            for block in response.content
            if block.type == "tool_use"
        ]
        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "",
            content=list(response.content),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def extract(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 8192,
        effort: str | None = None,
    ) -> T:
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_format": schema,
        }
        if effort:
            params["output_config"] = {"effort": effort}

        try:
            response = _call(self._client.messages.parse, **params)
        except ValueError as error:  # pydantic could not read the reply as the schema
            raise LLMOutputError("the reply did not match the requested shape") from error
        _check_stop(response.stop_reason)
        if response.parsed_output is None:
            raise LLMOutputError("the reply did not match the requested shape")
        return response.parsed_output


def _check_stop(stop_reason: str | None) -> None:
    if stop_reason == "refusal":
        raise LLMRefused("the model declined this request")
    if stop_reason == "max_tokens":
        raise LLMOutputError("the reply was cut off at the token limit")


def _call(function, **params):
    try:
        return function(**params)
    except (anthropic.APIConnectionError, anthropic.RateLimitError) as error:
        # APITimeoutError is a subclass of APIConnectionError.
        raise LLMUnavailable(type(error).__name__) from error
    except anthropic.APIStatusError as error:
        if error.status_code >= 500:
            raise LLMUnavailable(f"server error {error.status_code}") from error
        raise LLMError(f"request rejected ({error.status_code})") from error


@lru_cache
def _build_llm(settings: Settings) -> AnthropicLLM:
    return AnthropicLLM(settings.anthropic_api_key, settings.llm_timeout_seconds)


def get_llm() -> LLM:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set")
    return _build_llm(settings)
