from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlmodel import Session

from app.enrichment.openfda import OpenFdaClient
from app.enrichment.rxnorm import RxNormClient


class ToolError(Exception):
    """A tool could not do its job. The message is plain and is handed to the model."""


class NoInput(BaseModel):
    """For tools that take no arguments: they always work on the signed-in patient."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ToolContext:
    """What a tool may touch. The patient is fixed by the server, never chosen by the model."""

    db: Session
    patient_id: str
    rxnorm: RxNormClient | None = None
    openfda: OpenFdaClient | None = None
    search: Any = None  # a DocumentSearch (see profile_tools.py), added with the retriever


@dataclass(frozen=True)
class Tool:
    """One tool described MCP-style: a name, a description, an input schema, a typed result."""

    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[ToolContext, Any], BaseModel]

    def spec(self) -> dict[str, Any]:
        """The shape the Anthropic API expects for one tool."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }


class ToolRegistry:
    """The one list of tools. An agent gets a smaller one made with `only` (least privilege)."""

    def __init__(self, tools: Iterable[Tool]) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Two tools are called {tool.name}")
            self._tools[tool.name] = tool

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def specs(self) -> list[dict[str, Any]]:
        return [tool.spec() for tool in self._tools.values()]

    def only(self, names: Iterable[str]) -> "ToolRegistry":
        return ToolRegistry(self._tools[name] for name in names)

    def run(self, name: str, raw_input: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        """Run one tool call from the model. Always returns {"ok": ...}; never raises for bad calls.

        Error messages never repeat the model's input, because it can hold patient text.
        """
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": "There is no tool with that name."}
        try:
            arguments = tool.input_model.model_validate(raw_input)
        except ValidationError:
            return {"ok": False, "error": "The tool input was not valid. Check the schema."}
        try:
            result = tool.handler(context, arguments)
        except ToolError as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "data": result.model_dump(mode="json")}
