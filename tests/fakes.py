from typing import Any, TypeVar

from pydantic import BaseModel

from app.llm import LLMResponse

T = TypeVar("T", bound=BaseModel)


class FakeLLM:
    """A scripted stand-in for app.llm: no network, and every call is recorded."""

    def __init__(self, *, extractions: list | None = None, replies: list | None = None) -> None:
        self._extractions = list(extractions or [])
        self._replies = list(replies or [])
        self.calls: list[dict[str, Any]] = []

    def extract(self, *, model, system, user, schema: type[T], max_tokens=8192, effort=None) -> T:
        self.calls.append(
            {"kind": "extract", "model": model, "system": system, "user": user, "schema": schema}
        )
        item = self._extractions.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def complete(
        self, *, model, system, messages, tools=None, max_tokens=4096, effort=None
    ) -> LLMResponse:
        self.calls.append(
            {
                "kind": "complete",
                "model": model,
                "system": system,
                "messages": list(messages),
                "tools": tools,
                "effort": effort,
            }
        )
        item = self._replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
