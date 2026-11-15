"""The full-path eval, run against the real question graph with a scripted fake model.

No model, no internet, no embedding model. These prove that `--full-path` really goes through the
gate, router, tools and validators, and that what it scores is what the app did.
"""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.agents.question_graph import QuestionResult, Route
from app.llm import LLMResponse, LLMUnavailable, ToolCall
from app.qa.retriever import Retriever
from tests.auth.helpers import make_settings
from tests.eval import full_path
from tests.eval.full_path import (
    FALLBACK,
    OUT_OF_SCOPE,
    REDIRECT,
    action_taken,
    build_world,
    dry_run_report,
    run_full_path,
)
from tests.eval.run_eval import load_cases
from tests.fakes import FakeLLM

# Keyword search only: no test loads the real embedding model.
SETTINGS = make_settings(embeddings_enabled=False)
GOOD_S1 = (
    "Your discharge papers say your water pill, furosemide, is now 40 mg once a day in the "
    "morning. [D1] It was 20 mg before. [D1]\n<followups>\n- When do I take it?\n</followups>"
)


def case(case_id: str) -> dict:
    return next(c for c in load_cases()[0] if c["id"] == case_id)


def say(text: str) -> LLMResponse:
    return LLMResponse(
        text=text, tool_calls=[], stop_reason="end_turn", content=[{"type": "text", "text": text}]
    )


def search(query: str) -> LLMResponse:
    arguments = {"query": query}
    block = {"type": "tool_use", "id": "t1", "name": "search_patient_document", "input": arguments}
    call = ToolCall(id="t1", name="search_patient_document", input=arguments)
    return LLMResponse(text="", tool_calls=[call], stop_reason="tool_use", content=[block])


def run(llm: FakeLLM, case_id: str, **changes):
    _, forbidden = load_cases()
    options = {
        "version": "v7", "cases": [case(case_id)], "global_forbidden": forbidden, "runs": 1,
        "workers": 1, "claims": False, "budget_dollars": 5.0,
    }  # fmt: skip
    return run_full_path(llm, SETTINGS, **{**options, **changes})


def script_ordinary_question(llm: FakeLLM, answer: str) -> None:
    for _ in range(3):  # the safety classifier runs three times
        llm.queue_reply(say("TIER 3"))
    llm.queue_extraction(
        Route(
            route="MEDICINE",
            rewritten_question="What changed with my water pill?",
            focus_medicine="furosemide",
        )
    )
    llm.queue_reply(search("furosemide"))
    llm.queue_reply(say(answer))


def test_an_emergency_gets_the_fixed_911_text_from_the_gate_with_no_model_call():
    llm = FakeLLM()

    [result] = run(llm, "T6")

    assert result.got == "Call 911" and result.passed
    assert result.version == "v7+graph"
    assert llm.calls == []


def test_an_ordinary_question_goes_through_router_search_and_validators():
    llm = FakeLLM()
    script_ordinary_question(llm, GOOD_S1)

    [result] = run(llm, "S1")

    assert result.error is None and result.checks == []
    assert result.got == "Just answer"
    assert result.facts_found == result.facts_total and result.passed
    answer_calls = [c for c in llm.calls if c["kind"] == "complete" and c["tools"]]
    assert {tool["name"] for tool in answer_calls[0]["tools"]} == {
        "get_confirmed_medicines",
        "search_patient_document",
        "search_fda_label",
        "lookup_rxnorm",
    }


def test_the_search_tool_returns_only_this_patients_passages():
    llm = FakeLLM()
    script_ordinary_question(llm, GOOD_S1)

    run(llm, "S1")

    result_turn = next(c for c in llm.calls if c["kind"] == "complete" and len(c["messages"]) > 1)
    returned = str(result_turn["messages"][-1]["content"])
    assert "furosemide" in returned.casefold()
    assert "Prinivil" not in returned  # Patient 3's papers


def test_a_model_failure_shows_up_as_a_fallback_not_as_an_answer():
    llm = FakeLLM()
    for _ in range(3):
        llm.queue_reply(say("TIER 3"))
    llm.queue_extraction(LLMUnavailable())  # the router fails: the question goes to the agent
    llm.queue_reply(LLMUnavailable())  # and so does the agent

    [result] = run(llm, "S1")

    assert result.got == FALLBACK
    assert not result.action_ok and not result.passed


def test_a_checks_failure_in_the_graph_is_reported_with_its_names():
    llm = FakeLLM()
    cited_nothing = "Your discharge papers say furosemide is 40 mg once a day in the morning."
    script_ordinary_question(llm, cited_nothing)
    llm.queue_reply(say(cited_nothing))  # the retry fails the same way

    [result] = run(llm, "S1")

    assert result.got == FALLBACK
    assert result.checks  # the validators' check names, taken from the graph run


def test_the_budget_stops_new_questions():
    [result] = run(FakeLLM(), "S1", budget_dollars=0.0)

    assert result.got == "SKIPPED" and result.skipped


def test_each_outcome_maps_to_an_action_that_is_never_an_expected_one():
    def outcome(name: str, reply: str = "ok") -> QuestionResult:
        return QuestionResult(
            reply=reply, followups=[], citations=[], outcome=name, tier=3, decided_by="",
            task="", focus_medicine=None, tool_names=[], failed_checks=[], attempts=0,
            retrieval_mode="", fallback_reason=None, gate_ms=0, total_ms=0,
        )  # fmt: skip

    assert action_taken(outcome("emergency")) == "Call 911"
    assert action_taken(outcome("fallback")) == FALLBACK
    assert action_taken(outcome("redirect")) == REDIRECT
    assert action_taken(outcome("out_of_scope")) == OUT_OF_SCOPE
    assert action_taken(outcome("answered", "Call your care team: 010-0311")) == "Call care team"


def test_each_patient_has_only_their_own_chunks():
    with tempfile.TemporaryDirectory() as folder:
        world = build_world(["P1", "P3"], SETTINGS, Path(folder))
        try:
            with Session(world.engine) as db:
                retriever = Retriever(db)
                p1 = retriever.search(world.patient_ids["P1"], "Prinivil lisinopril", 10)
                p3 = retriever.search(world.patient_ids["P3"], "Prinivil lisinopril", 10)
        finally:
            world.engine.dispose()  # Windows cannot delete the file while it is open

    assert all("Prinivil" not in passage.text for passage in p1)
    assert any("Prinivil" in passage.text for passage in p3)


def test_the_dry_run_report_covers_every_case_and_calls_no_model():
    cases, _ = load_cases()

    report = dry_run_report(cases, SETTINGS, runs=3, version="v7", claims=False)

    assert "33 cases x 3 runs = 99 questions" in report
    assert all(c["id"] in report for c in cases)
    assert "P1-U1" in report and "P1-U2" in report


# --- the database file must be closed before its folder is removed (Windows cannot delete an
# open file; this checks the order on every system) ---


def _record_close_and_cleanup(monkeypatch) -> list[str]:
    events: list[str] = []
    real_dispose = Engine.dispose

    def dispose(self, *args, **kwargs):
        events.append("dispose")
        return real_dispose(self, *args, **kwargs)

    class Recording(tempfile.TemporaryDirectory):
        def cleanup(self):
            events.append("folder removed")
            super().cleanup()

    monkeypatch.setattr(Engine, "dispose", dispose)
    monkeypatch.setattr(full_path.tempfile, "TemporaryDirectory", Recording)
    return events


def test_the_engine_is_closed_before_the_folder_is_removed_in_a_real_run(monkeypatch):
    events = _record_close_and_cleanup(monkeypatch)

    run(FakeLLM(), "T6")

    assert events == ["dispose", "folder removed"]


def test_the_engine_is_closed_before_the_folder_is_removed_in_a_dry_run(monkeypatch):
    events = _record_close_and_cleanup(monkeypatch)
    cases, _ = load_cases()

    dry_run_report(cases[:1], SETTINGS, runs=1, version="v7", claims=False)

    assert events == ["dispose", "folder removed"]


def test_the_engine_is_closed_before_the_folder_is_removed_even_when_the_run_fails(monkeypatch):
    events = _record_close_and_cleanup(monkeypatch)
    monkeypatch.setattr(full_path, "run_once", lambda *a, **k: 1 / 0)

    with pytest.raises(ZeroDivisionError):
        run(FakeLLM(), "T6")

    assert events == ["dispose", "folder removed"]
