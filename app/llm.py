import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from app.config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


DETAIL_MAX_CHARS = 200
_API_KEY = re.compile(r"sk-[A-Za-z0-9_-]+")


class LLMError(Exception):
    """Base class. Messages never contain prompts or patient text.

    `detail` is a short, one-line, already-cleaned reason that is safe to show a developer in the
    eval output. It is optional; without it, it is just the class name.
    """

    def __init__(self, message: str = "", detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail or type(self).__name__


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
            raise LLMOutputError(
                "the reply did not match the requested shape",
                detail="LLMOutputError reason=bad_shape",
            ) from error
        _check_stop(response.stop_reason)
        if response.parsed_output is None:
            raise LLMOutputError(
                "the reply did not match the requested shape",
                detail="LLMOutputError reason=bad_shape",
            )
        return response.parsed_output


def _check_stop(stop_reason: str | None) -> None:
    if stop_reason == "refusal":
        raise LLMRefused("the model declined this request", detail="LLMRefused stop=refusal")
    if stop_reason == "max_tokens":
        raise LLMOutputError(
            "the reply was cut off at the token limit", detail="LLMOutputError stop=max_tokens"
        )


def _one_line(text: str) -> str:
    """Redact key-like strings, then drop the characters that break a CSV or a markdown table."""
    text = _API_KEY.sub("[redacted-key]", text)
    return " ".join(text.replace("|", " ").replace(",", " ").split())


def _safe_detail(error: Exception) -> str:
    """Class, HTTP status, API error type and the API's own message, on one short line.

    Built only from the response the API sent back, never from the request, so the prompt,
    the messages and the headers cannot get in.
    """
    parts = [type(error).__name__]
    status = getattr(error, "status_code", None)
    if status is not None:
        parts.append(f"status={status}")
    body = getattr(error, "body", None)
    api_error = body.get("error", body) if isinstance(body, dict) else None
    api_type = api_error.get("type") if isinstance(api_error, dict) else None
    if isinstance(api_type, str) and api_type != "error":
        parts.append(f"type={api_type}")
    api_message = getattr(error, "message", None)
    if isinstance(api_message, str) and api_message:
        parts.append(f"msg={api_message}")
    line = _one_line(" ".join(parts))
    if len(line) > DETAIL_MAX_CHARS:
        line = line[: DETAIL_MAX_CHARS - 1] + "…"
    return line


def _call(function, **params):
    try:
        return function(**params)
    except (anthropic.APIConnectionError, anthropic.RateLimitError) as error:
        # APITimeoutError is a subclass of APIConnectionError.
        raise LLMUnavailable(type(error).__name__, detail=_safe_detail(error)) from error
    except anthropic.APIStatusError as error:
        if error.status_code >= 500:
            raise LLMUnavailable(
                f"server error {error.status_code}", detail=_safe_detail(error)
            ) from error
        raise LLMError(
            f"request rejected ({error.status_code})", detail=_safe_detail(error)
        ) from error


@lru_cache
def _build_llm(settings: Settings) -> AnthropicLLM:
    return AnthropicLLM(settings.anthropic_api_key, settings.llm_timeout_seconds)


def get_llm() -> LLM:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set")
    return _build_llm(settings)
