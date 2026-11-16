"""The full-path eval, run against the real question graph with a scripted fake model.

No model, no internet, no embedding model. These prove that `--full-path` really goes through the
gate, router, tools and validators, and that what it scores is what the app did.
"""

import csv
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
from tests.eval import run_eval as eval_module
from tests.eval.full_path import (
    FALLBACK,
    OUT_OF_SCOPE,
    REDIRECT,
    action_taken,
    build_world,
    dry_run_report,
    run_full_path,
)
from tests.eval.run_eval import RunResult, load_cases, summarize, write_csv
from tests.fakes import FakeLLM

# Keyword search only: no test loads the real embedding model.
SETTINGS = make_settings(embeddings_enabled=False)
GOOD_S1 = (
    "Your discharge papers say your water pill, furosemide, is now 40 mg once a day in the "
    "morning. [D1] It was 20 mg before. [D1]\n<followups>\n- When do I take it?\n</followups>"
)


def run_result(**changes) -> RunResult:
    fields = {
        "version": "v7+graph", "case_id": "S1", "patient": "P1", "run": 1,
        "expected": "Just answer", "got": "Just answer", "facts_found": 1, "facts_total": 1,
        "forbidden": [], "checks": [], "words": 10, "unsupported": None, "error": None,
        "answer": "ok",
    }  # fmt: skip
    return RunResult(**{**fields, **changes})


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


# --- the eval explains its misses: what happened inside the graph, per run ---


def test_a_traced_run_records_the_gate_route_tools_and_timing():
    llm = FakeLLM()
    script_ordinary_question(llm, GOOD_S1)

    [result] = run(llm, "S1")

    assert result.gate_tier == 3 and result.decided_by == "classifier"
    assert result.classifier_failures == 0
    assert result.route == "MEDICINE" and result.tool_names == ["search_patient_document"]
    assert result.attempts == 1 and isinstance(result.total_ms, int)
    assert result.fallback_reason is None and result.fallback_detail is None


def test_an_emergency_is_traced_as_the_rules_with_no_route_or_tools():
    [result] = run(FakeLLM(), "T6")

    assert result.gate_tier == 1 and result.decided_by == "rules"
    assert result.classifier_failures == 0 and result.route == "NONE"
    assert result.tool_names == [] and result.attempts == 0


def test_a_failed_safety_reading_is_counted_and_makes_the_tier_2():
    llm = FakeLLM()
    llm.queue_reply(say("TIER 3"))
    llm.queue_reply(say("TIER 3"))
    llm.queue_reply(LLMUnavailable("down"))
    llm.queue_extraction(LLMUnavailable("down"))
    llm.queue_reply(LLMUnavailable("down"))

    [result] = run(llm, "S1")

    assert result.classifier_failures == 1 and result.gate_tier == 2


def test_a_model_failure_records_only_the_error_class_never_its_message():
    llm = FakeLLM()
    for _ in range(3):
        llm.queue_reply(say("TIER 3"))
    llm.queue_extraction(LLMUnavailable("secret patient text"))
    llm.queue_reply(LLMUnavailable("secret patient text"))

    [result] = run(llm, "S1")

    assert result.fallback_reason == "model_error"
    assert result.fallback_detail == "LLMUnavailable"
    assert "secret" not in str(result)


def test_the_csv_has_the_trace_columns_only_for_a_traced_run(tmp_path):
    traced = run_result(
        gate_tier=2, decided_by="classifier", classifier_failures=1, route="MEDICINE",
        tool_names=["search_patient_document", "get_confirmed_medicines"], attempts=2,
        fallback_reason="model_error", fallback_detail="LLMUnavailable", total_ms=1234,
    )  # fmt: skip

    write_csv([traced], tmp_path / "a.csv")
    write_csv([run_result()], tmp_path / "b.csv")

    (row,) = list(csv.DictReader((tmp_path / "a.csv").open(encoding="utf-8")))
    assert row["gate_tier"] == "2" and row["decided_by"] == "classifier"
    assert row["classifier_failures"] == "1" and row["route"] == "MEDICINE"
    assert row["tool_names"] == "search_patient_document get_confirmed_medicines"
    assert row["attempts"] == "2" and row["total_ms"] == "1234"
    assert row["fallback_reason"] == "model_error" and row["fallback_detail"] == "LLMUnavailable"
    assert "gate_tier" not in (tmp_path / "b.csv").read_text(encoding="utf-8").splitlines()[0]


def test_the_summary_counts_fallbacks_by_reason_and_totals_classifier_failures():
    results = [
        run_result(gate_tier=3, classifier_failures=0, fallback_reason="timeout"),
        run_result(
            gate_tier=2, classifier_failures=2, fallback_reason="model_error",
            fallback_detail="LLMUnavailable",
        ),
        run_result(
            gate_tier=2, classifier_failures=1, fallback_reason="model_error",
            fallback_detail="LLMUnavailable",
        ),
        run_result(gate_tier=3, classifier_failures=0, fallback_reason="validators"),
        run_result(gate_tier=3, classifier_failures=0),
    ]  # fmt: skip

    summary = summarize(results)

    assert "| timeout | 1 |" in summary and "| tool_limit | 0 |" in summary
    assert "| model_error (LLMUnavailable) | 2 |" in summary
    assert "| validators | 1 |" in summary and "| error | 0 |" in summary
    assert "Classifier failures** (a failed safety reading counts as Tier 2): 3 in 2 of 5" in (
        summary
    )
    assert "## By run" in summary and "| Gate tier |" in summary


def test_a_prompt_only_summary_has_no_trace_tables():
    assert "Fallbacks by reason" not in summarize([run_result()])


def test_the_header_shows_the_parallel_workers_and_the_default_is_4(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(full_path, "run_full_path", lambda *a, **k: [])
    monkeypatch.setattr(eval_module, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(eval_module, "get_llm", lambda: FakeLLM())

    eval_module.main(["--full-path", "--only", "T6", "--workers", "2"])
    assert "Parallel workers: 2" in capsys.readouterr().out

    eval_module.main(["--full-path", "--only", "T6"])
    assert "Parallel workers: 4" in capsys.readouterr().out
