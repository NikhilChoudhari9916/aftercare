from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.agents.question_graph import Route
from app.auth.dependencies import DbSession
from app.auth.session import COOKIE_NAME, hash_token
from app.config import get_settings
from app.llm import LLMResponse, ToolCall
from app.memory.session import get_session_memory
from app.models import Chunk, PatientAccess, QALog, Role, User
from app.qa.retriever import Retriever
from app.qa.routes import ToolClients, get_question_llm, get_retriever, get_tool_clients
from app.safety.messages import TIER1_MESSAGE
from tests.auth.helpers import FakeProvider, sign_in
from tests.documents.test_upload_api import owner
from tests.fakes import FakeLLM
from tests.qa.conftest import other_patient

NO_ANSWER = "Your papers and drug labels here don't answer this. Please ask your pharmacist."


@pytest.fixture(autouse=True)
def pretend_outside(app: FastAPI, llm: FakeLLM):
    """No real model or drug services, and keyword search only: no test needs the internet."""
    get_session_memory.cache_clear()
    app.dependency_overrides[get_question_llm] = lambda: llm
    app.dependency_overrides[get_tool_clients] = lambda: ToolClients(rxnorm=None, openfda=None)

    def keyword_retriever(db: DbSession) -> Retriever:
        return Retriever(db)

    app.dependency_overrides[get_retriever] = keyword_retriever
    yield
    get_session_memory.cache_clear()


def ask(client: TestClient, patient_id: str, question: str = "What is furosemide for?"):
    return client.post(f"/patients/{patient_id}/ask", json={"question": question})


def reply(text: str) -> LLMResponse:
    block = {"type": "text", "text": text}
    return LLMResponse(text=text, tool_calls=[], stop_reason="end_turn", content=[block])


def tool_call(query: str) -> LLMResponse:
    arguments = {"query": query}
    block = {"type": "tool_use", "id": "t1", "name": "search_patient_document", "input": arguments}
    call = ToolCall(id="t1", name="search_patient_document", input=arguments)
    return LLMResponse(text="", tool_calls=[call], stop_reason="tool_use", content=[block])


def script_question(llm: FakeLLM, answer: str, *, rewritten: str = "What is furosemide for?"):
    """What the fake model says for one ordinary question: three safety runs, the router,
    a search, then the answer. (The safety runs take the first three replies.)"""
    for _ in range(3):
        llm.queue_reply(reply("TIER 3"))
    llm.queue_extraction(
        Route(route="MEDICINE", rewritten_question=rewritten, focus_medicine="furosemide")
    )
    llm.queue_reply(tool_call("furosemide"))
    llm.queue_reply(reply(answer))


def cited_answer(db: Session, patient_id: str) -> tuple[str, str]:
    """A good answer that cites a passage which really exists for this patient: (ref, text)."""
    chunks = db.exec(select(Chunk).where(Chunk.patient_id == patient_id)).all()
    ref = next(chunk.ref for chunk in chunks if "furosemide" in chunk.text.casefold())
    text = (
        "<analysis>checked</analysis>\n"
        "Your discharge papers say to take "
        f"**furosemide, 40 mg, once a day in the morning**. [{ref}]\n"
        "<followups>\n- What changed?\n</followups>"
    )
    return ref, text


# --- the answer ---


def test_an_emergency_gets_the_fixed_words_with_no_model_call(
    client: TestClient, confirmed_patient: str, llm: FakeLLM, db: Session
):
    calls_before = len(llm.calls)

    response = ask(client, confirmed_patient, "my chest hurts really badly")

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "emergency"
    assert body["answer"] == TIER1_MESSAGE
    assert body["tier"] == 1
    assert body["citations"] == [] and body["followups"] == []
    assert len(llm.calls) == calls_before
    row = db.exec(select(QALog)).one()
    assert (row.tier, row.outcome, row.tool_calls) == (1, "emergency", 0)


def test_a_cited_answer_comes_back_with_its_source_and_a_log_row_without_text(
    client: TestClient, confirmed_patient: str, llm: FakeLLM, db: Session
):
    ref, answer = cited_answer(db, confirmed_patient)
    script_question(llm, answer)

    response = ask(client, confirmed_patient)

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "answered" and body["tier"] == 3
    assert [c["id"] for c in body["citations"]] == [ref]
    assert body["citations"][0]["label"].startswith("From your papers, page")
    assert body["followups"] == ["What changed?"]
    assert "<analysis>" not in body["answer"]

    row = db.exec(select(QALog)).one()
    assert (row.task, row.outcome, row.attempts) == ("MEDICINE", "answered", 1)
    assert row.tool_names == '["search_patient_document"]' and row.tool_calls == 1
    assert row.cited_ids == f'["{ref}"]'
    assert row.retrieval_mode == "keyword"
    stored = " ".join(str(value) for value in row.model_dump().values()).casefold()
    assert "furosemide" not in stored and "what is" not in stored  # no question, no answer


def test_a_second_question_can_say_it_and_the_first_one_is_remembered(
    client: TestClient, confirmed_patient: str, llm: FakeLLM, db: Session
):
    _, answer = cited_answer(db, confirmed_patient)
    script_question(llm, answer)
    ask(client, confirmed_patient, "What is furosemide for?")
    script_question(llm, answer, rewritten="Can I take furosemide at night?")

    ask(client, confirmed_patient, "Can I take it at night?")

    second_router_call = [call for call in llm.calls if call["kind"] == "extract"][-1]
    assert "What is furosemide for?" in second_router_call["user"]
    assert "Can I take it at night?" in second_router_call["user"]


def test_an_emergency_is_not_remembered(
    client: TestClient, confirmed_patient: str, llm: FakeLLM, db: Session
):
    ask(client, confirmed_patient, "my chest hurts really badly")
    _, answer = cited_answer(db, confirmed_patient)
    script_question(llm, answer)

    ask(client, confirmed_patient)

    router_call = [call for call in llm.calls if call["kind"] == "extract"][-1]
    assert "<recent_conversation>\n(none)\n</recent_conversation>" in router_call["user"]


def test_two_failed_answers_give_the_fallback_and_a_log_row(
    client: TestClient, confirmed_patient: str, llm: FakeLLM, db: Session
):
    bad = (
        "Your discharge papers say to take "
        "**furosemide, 40 mg, once a day in the morning**. [D99]"
    )
    script_question(llm, bad)
    llm.queue_reply(reply(bad))

    body = ask(client, confirmed_patient).json()

    assert body["outcome"] == "fallback"
    assert body["answer"].startswith("I can't answer that safely")
    row = db.exec(select(QALog)).one()
    assert row.outcome == "fallback" and row.attempts == 2
    assert "UNKNOWN_CITATION" in row.validator_checks


# --- who may ask ---


def test_an_aide_may_ask(
    client: TestClient,
    new_client: Callable[[], TestClient],
    provider: FakeProvider,
    confirmed_patient: str,
    db: Session,
):
    aide = new_client()
    sign_in(aide, provider, sub="aide", email="aide@example.com")
    aide_user = db.exec(select(User).where(User.google_sub == "aide")).one()
    db.add(PatientAccess(patient_id=confirmed_patient, user_id=aide_user.id, role=Role.AIDE))
    db.commit()

    response = ask(aide, confirmed_patient, "my chest hurts really badly")

    assert response.status_code == 200
    assert response.json()["outcome"] == "emergency"


def test_a_stranger_and_a_signed_out_visitor_are_refused(
    new_client: Callable[[], TestClient], provider: FakeProvider, confirmed_patient: str
):
    assert ask(new_client(), confirmed_patient).status_code == 401
    stranger = new_client()
    sign_in(stranger, provider, sub="stranger", email="s@example.com")

    assert ask(stranger, confirmed_patient).status_code == 404


def test_papers_that_are_not_confirmed_cannot_be_asked_about(
    client: TestClient, provider: FakeProvider
):
    patient_id = owner(client, provider)

    response = ask(client, patient_id)

    assert response.status_code == 404
    assert "not been confirmed" in response.json()["detail"]


@pytest.mark.parametrize("question", ["x" * 501, "   "])
def test_an_empty_or_too_long_question_is_refused_kindly(
    client: TestClient, confirmed_patient: str, question: str
):
    response = ask(client, confirmed_patient, question)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


# --- the two-patient leak test, on the new endpoint (ADR-0031) ---


def test_a_question_never_finds_another_patients_papers(
    client: TestClient, confirmed_patient: str, llm: FakeLLM, db: Session
):
    other_id = other_patient(db)  # a second patient whose only medicine is warfarin
    theirs = db.exec(select(Chunk).where(Chunk.patient_id == other_id)).all()
    assert any("warfarin" in chunk.text.casefold() for chunk in theirs)
    for _ in range(3):
        llm.queue_reply(reply("TIER 3"))
    llm.queue_extraction(Route(route="MEDICINE", rewritten_question="what is warfarin for"))
    llm.queue_reply(tool_call("warfarin"))
    llm.queue_reply(reply(NO_ANSWER))

    body = ask(client, confirmed_patient, "what is warfarin for").json()

    searched = [call for call in llm.calls if call["kind"] == "complete"][-1]
    returned = searched["messages"][-1]["content"][0]["content"]
    assert "warfarin" not in returned.casefold()  # the tool found nothing of the other patient's
    assert body["outcome"] == "answered"
    assert ask(client, other_id).status_code == 404  # and cannot ask as the other patient either


def without_the_ai_service(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use the real, lazy model lookup with no key set, even if the developer has one."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    del app.dependency_overrides[get_question_llm]


def test_a_keyword_emergency_gets_its_fixed_text_even_when_the_ai_service_is_not_set_up(
    app: FastAPI, client: TestClient, confirmed_patient: str, monkeypatch: pytest.MonkeyPatch
):
    without_the_ai_service(app, monkeypatch)

    response = ask(client, confirmed_patient, "my chest hurts really badly")

    assert response.status_code == 200
    assert response.json()["answer"] == TIER1_MESSAGE


def test_an_ordinary_question_without_the_ai_service_gets_the_safe_fallback(
    app: FastAPI, client: TestClient, confirmed_patient: str, monkeypatch: pytest.MonkeyPatch
):
    without_the_ai_service(app, monkeypatch)

    body = ask(client, confirmed_patient).json()

    assert body["outcome"] == "fallback"
    assert body["tier"] == 2  # the gate could not run its classifier, so it chose the safer tier


# --- F3: a possible emergency gets the 911 words before any refusal ---

LONG_EMERGENCY = "my chest hurts really badly. " + "I have been resting at home. " * 30


def test_an_emergency_gets_the_911_words_even_when_the_papers_are_not_confirmed(
    client: TestClient, provider: FakeProvider, llm: FakeLLM, db: Session
):
    patient_id = owner(client, provider)  # signed in, nothing confirmed yet
    calls_before = len(llm.calls)

    response = ask(client, patient_id, "my chest hurts really badly")

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "emergency" and body["tier"] == 1
    assert body["answer"] == TIER1_MESSAGE
    assert body["citations"] == [] and body["followups"] == []
    assert len(llm.calls) == calls_before  # no model was asked
    row = db.exec(select(QALog)).one()
    assert row.patient_id == patient_id
    assert (row.tier, row.decided_by, row.task, row.outcome, row.tool_calls) == (
        1,
        "rules",
        "NONE",
        "emergency",
        0,
    )
    session_key = hash_token(client.cookies.get(COOKIE_NAME))
    assert get_session_memory().recall(session_key, patient_id).turns == ()  # nothing remembered


def test_a_long_emergency_gets_the_911_words_not_a_length_refusal(
    client: TestClient, confirmed_patient: str, llm: FakeLLM
):
    assert len(LONG_EMERGENCY) > get_settings().max_question_chars
    calls_before = len(llm.calls)  # the fixture's own document reading is already in there

    response = ask(client, confirmed_patient, LONG_EMERGENCY)

    assert response.status_code == 200
    assert response.json()["answer"] == TIER1_MESSAGE
    assert len(llm.calls) == calls_before


def test_a_long_emergency_before_confirming_also_gets_the_911_words(
    client: TestClient, provider: FakeProvider
):
    patient_id = owner(client, provider)

    response = ask(client, patient_id, LONG_EMERGENCY)

    assert response.status_code == 200
    assert response.json()["outcome"] == "emergency"


def test_an_ordinary_question_before_confirming_is_still_refused_with_404(
    client: TestClient, provider: FakeProvider, db: Session
):
    patient_id = owner(client, provider)

    response = ask(client, patient_id, "x" * 600)

    assert response.status_code == 404
    assert db.exec(select(QALog)).all() == []  # a refusal writes no row, as before


def test_a_stranger_still_gets_404_for_an_emergency_question(
    new_client: Callable[[], TestClient], provider: FakeProvider, confirmed_patient: str
):
    stranger = new_client()
    sign_in(stranger, provider, sub="stranger", email="s@example.com")

    assert ask(stranger, confirmed_patient, "my chest hurts really badly").status_code == 404
