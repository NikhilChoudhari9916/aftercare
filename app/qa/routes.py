"""POST /patients/{id}/ask: one question in, one cited answer out (ADR-0035, ADR-0036).

An owner or an aide may ask (ADR-0032). The route only checks who is asking, loads what the
graph needs and writes one QALog row; the decisions are made in app/agents/question_graph.py.
This is a plain `def`, so FastAPI runs it in a worker thread, which is where the safety
gate wants to run (ADR-0041).
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.agents.question_graph import (
    MEDICATION_TOOLS,
    Citation,
    QuestionDeps,
    QuestionResult,
    run_question,
)
from app.auth.dependencies import AppSettings, CurrentUser, DbSession, require_access
from app.auth.session import COOKIE_NAME, hash_token
from app.enrichment import get_openfda, get_rxnorm
from app.enrichment.openfda import OpenFdaClient
from app.enrichment.rxnorm import RxNormClient
from app.llm import LLM, LLMResponse, get_llm
from app.memory.session import SessionMemory, get_session_memory
from app.models import PatientAccess, QALog, Role
from app.prompts import load_prompt
from app.qa.answer_text import plain_text
from app.qa.factory import build_retriever
from app.qa.profile_text import render_profile_text
from app.qa.prompts import load_answer_prompt
from app.qa.retriever import Retriever
from app.safety.context import PatientSafetyContext, safety_context
from app.safety.gate import run_gate
from app.safety.messages import TIER1_MESSAGE
from app.safety.rules import Tier, apply_rules
from app.summary.profile import load_confirmed_profile
from app.tools import ToolContext, default_registry

logger = logging.getLogger(__name__)

router = APIRouter()

# An aide may ask questions too (ADR-0032), so owner and aide are both allowed.
Asker = Annotated[PatientAccess, Depends(require_access(Role.OWNER, Role.AIDE))]


class AskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The real limit is Settings.max_question_chars; this only stops an absurd request early.
    question: str = Field(min_length=1, max_length=5000)


class AskOut(BaseModel):
    answer: str  # with its [D1] / [L1] tags still in it; the UI turns them into small labels
    followups: list[str]
    citations: list[Citation]
    tier: Literal[1, 2, 3]
    outcome: str


@dataclass(frozen=True)
class ToolClients:
    """The outside services the tools may call. Tests replace this with pretend ones."""

    rxnorm: RxNormClient | None
    openfda: OpenFdaClient | None


class LazyLLM:
    """Looks up the real model only when something calls it.

    A question the keyword rules already know is an emergency must still get its fixed 911 text
    when the AI service is not set up or is down, so the model is not a requirement of the
    request. If it is unavailable when called, the gate counts that as Tier 2, the router sends
    the question to the agent, and the agent's step ends in the safe fallback.
    """

    def complete(self, **kwargs: Any) -> LLMResponse:
        return get_llm().complete(**kwargs)

    def extract(self, **kwargs: Any) -> Any:
        return get_llm().extract(**kwargs)


def get_question_llm() -> LLM:
    return LazyLLM()


def get_tool_clients() -> ToolClients:
    return ToolClients(rxnorm=get_rxnorm(), openfda=get_openfda())


def get_retriever(db: DbSession, settings: AppSettings) -> Retriever:
    return build_retriever(db, settings)


def _log_row(patient_id: str, user_id: str, result: QuestionResult) -> QALog:
    """IDs, names, counts and timings only. Never the question or the answer (ADR-0031)."""
    return QALog(
        patient_id=patient_id,
        user_id=user_id,
        tier=result.tier,
        decided_by=result.decided_by,
        task=result.task,
        outcome=result.outcome,
        cited_ids=json.dumps([c.id for c in result.citations]),
        tool_names=json.dumps(result.tool_names),
        tool_calls=len(result.tool_names),
        validator_checks=json.dumps(result.failed_checks),
        attempts=result.attempts,
        retrieval_mode=result.retrieval_mode,
        gate_ms=result.gate_ms,
        total_ms=result.total_ms,
    )


def _emergency_result(gate_ms: int) -> QuestionResult:
    """The same result the graph's emergency step gives, for an emergency found before the graph."""
    return QuestionResult(
        reply=TIER1_MESSAGE,
        followups=[],
        citations=[],
        outcome="emergency",
        tier=int(Tier.EMERGENCY),
        decided_by="rules",
        task="NONE",
        focus_medicine=None,
        tool_names=[],
        failed_checks=[],
        attempts=0,
        retrieval_mode="",
        fallback_reason=None,
        gate_ms=gate_ms,
        total_ms=gate_ms,
    )


@router.post("/patients/{patient_id}/ask", response_model=AskOut)
def ask(
    patient_id: str,
    body: AskIn,
    request: Request,
    _access: Asker,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    llm: Annotated[LLM, Depends(get_question_llm)],
    clients: Annotated[ToolClients, Depends(get_tool_clients)],
    retriever: Annotated[Retriever, Depends(get_retriever)],
    memory: Annotated[SessionMemory, Depends(get_session_memory)],
) -> AskOut:
    profile = load_confirmed_profile(db, patient_id)
    # A possible emergency gets the fixed 911 words before any refusal below (an unconfirmed
    # profile, a long question). Without a profile only the shared red-flag list can apply.
    begun = time.monotonic()
    context = safety_context(profile) if profile is not None else PatientSafetyContext()
    if apply_rules(body.question, context).tier == Tier.EMERGENCY:
        emergency = _emergency_result(int((time.monotonic() - begun) * 1000))
        db.add(_log_row(patient_id, user.id, emergency))  # IDs only; nothing is remembered
        db.commit()
        return AskOut(
            answer=emergency.reply,
            followups=[],
            citations=[],
            tier=emergency.tier,
            outcome=emergency.outcome,
        )
    if profile is None:
        raise HTTPException(status_code=404, detail="The papers have not been confirmed yet")
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Please type a question.")
    if len(question) > settings.max_question_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Please keep your question under {settings.max_question_chars} characters.",
        )

    session_key = hash_token(request.cookies.get(COOKIE_NAME, ""))
    deps = QuestionDeps(
        llm=llm,
        settings=settings,
        profile=profile,
        profile_text=render_profile_text(profile),
        answer_template=load_answer_prompt(settings.answer_prompt_version),
        router_prompt=load_prompt(f"router_system_prompt_{settings.router_prompt_version}.txt"),
        registry=default_registry().only(MEDICATION_TOOLS),
        tools=ToolContext(
            db=db,
            patient_id=patient_id,  # fixed by the server: the model cannot ask for anyone else
            rxnorm=clients.rxnorm,
            openfda=clients.openfda,
            search=retriever,
        ),
        gate=lambda text: run_gate(text, context, llm=llm, settings=settings),
        recall=memory.recall(session_key, patient_id),
    )
    result = run_question(deps, question)

    if result.outcome in ("answered", "redirect", "out_of_scope"):
        # An emergency or a failed answer is never remembered: memory is ignored on the
        # urgent path (ADR-0029), and a refused answer is not a fact.
        memory.remember(
            session_key, patient_id, question, plain_text(result.reply), result.focus_medicine
        )

    db.add(_log_row(patient_id, user.id, result))
    db.commit()
    return AskOut(
        answer=result.reply,
        followups=result.followups,
        citations=result.citations,
        tier=result.tier,
        outcome=result.outcome,
    )
