import json
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
        self.grounding_reports: list[Any] = []

    def queue_extraction(self, item) -> None:
        self._extractions.append(item)

    def queue_reply(self, item) -> None:
        self._replies.append(item)

    def extract(self, *, model, system, user, schema: type[T], max_tokens=8192, effort=None) -> T:
        self.calls.append(
            {"kind": "extract", "model": model, "system": system, "user": user, "schema": schema}
        )
        if schema.__name__ == "GroundingVerdict":
            # This is an orchestration stub, not a semantic evaluator. Grounding tests queue
            # explicit supported/unsupported/malformed reports to exercise the actual guard.
            if self.grounding_reports:
                result = self.grounding_reports.pop(0)
                if isinstance(result, Exception):
                    raise result
                return result
            request = json.loads(user)
            return schema.model_validate(
                {
                    "claims": [
                        {
                            "claim_id": claim["id"],
                            "supported": True,
                            "evidence": [
                                {"source_id": cid, "quote": request["paper_passages"][cid]}
                                for cid in claim["source_ids"]
                            ],
                        }
                        for claim in request["claims"]
                    ]
                }
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
