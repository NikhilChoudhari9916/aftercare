import pytest
from pydantic import BaseModel, ConfigDict

from app.tools import ToolRegistry, default_registry
from app.tools.registry import NoInput, Tool, ToolContext, ToolError


class Echo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str


class Reply(BaseModel):
    said: str


def _echo(_context: ToolContext, arguments: Echo) -> Reply:
    if arguments.word == "fail":
        raise ToolError("It did not work.")
    return Reply(said=arguments.word)


ECHO = Tool("echo", "Repeat a word.", Echo, _echo)
CONTEXT = ToolContext(db=None, patient_id="p")  # these tools never touch the database


def test_every_tool_is_described_the_way_the_model_api_expects():
    specs = default_registry().specs()

    assert [s["name"] for s in specs] == [
        "get_confirmed_medicines",
        "get_schedule",
        "search_patient_document",
        "search_fda_label",
        "lookup_rxnorm",
    ]
    for spec in specs:
        assert spec["description"]
        assert spec["input_schema"]["type"] == "object"


def test_a_tool_that_works_returns_its_result_as_plain_data():
    assert ToolRegistry([ECHO]).run("echo", {"word": "hi"}, CONTEXT) == {
        "ok": True,
        "data": {"said": "hi"},
    }


def test_a_tool_that_cannot_do_its_job_returns_its_plain_message():
    result = ToolRegistry([ECHO]).run("echo", {"word": "fail"}, CONTEXT)

    assert result == {"ok": False, "error": "It did not work."}


def test_a_name_that_is_not_a_tool_is_refused():
    assert not ToolRegistry([ECHO]).run("delete_everything", {}, CONTEXT)["ok"]


def test_input_that_does_not_fit_the_schema_is_refused_without_repeating_it():
    registry = ToolRegistry([ECHO])
    for bad in ({}, {"word": 5}, {"word": "hi", "patient_id": "someone-else"}):
        result = registry.run("echo", bad, CONTEXT)
        assert result["ok"] is False
        assert "someone-else" not in result["error"]


def test_an_agent_gets_only_the_tools_it_is_given():
    medication = default_registry().only(["get_confirmed_medicines", "search_fda_label"])

    assert medication.names == ["get_confirmed_medicines", "search_fda_label"]
    assert not medication.run("get_schedule", {}, CONTEXT)["ok"]
    with pytest.raises(KeyError):
        default_registry().only(["no_such_tool"])


def test_two_tools_cannot_share_a_name():
    with pytest.raises(ValueError, match="echo"):
        ToolRegistry([ECHO, ECHO])


def test_a_tool_without_arguments_refuses_extra_ones():
    tool = Tool("ping", "Say pong.", NoInput, lambda _c, _a: Reply(said="pong"))

    assert ToolRegistry([tool]).run("ping", {}, CONTEXT)["ok"]
    assert not ToolRegistry([tool]).run("ping", {"patient_id": "x"}, CONTEXT)["ok"]
