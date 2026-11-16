"""Workflow 2: one question in, one safe, cited answer out (ADR-0035, ADR-0036).

    safety_gate -> (Tier 1: fixed 911 text, end)
                -> load_context -> router -> (schedule or out of scope: a fixed reply, end)
                -> agent <-> tools   (the ReAct loop: the model asks for a tool, we run it, repeat)
                -> validators -> (pass: finalize) (fail once: retry) (fail twice: fallback)

The safety gate and the validators are nodes WE wire in. The agent's tool list never contains
them and no edge skips them, so no model can decide to bypass a safety check (ADR-0004). Every
limit (6 tool calls, 30 seconds, a failed model call, two failed answers) ends in the safe
fallback message. Nodes are plain functions that take state and return what they add, so each
one can be tested without the graph.

Nothing in the result or in the logs holds patient text except the answer the patient is meant
to read (ADR-0031).
"""

import json
import logging
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.config import Settings
from app.extraction.schema import ExtractedContact
from app.llm import LLM, LLMError, LLMResponse
from app.memory.session import Recall
from app.qa.answer_text import cited_ids, parse_answer, plain_text
from app.qa.prompts import fill_prompt
from app.qa.sources import PAPERS, SourceBook
from app.qa.validators import ValidationResult, fallback_message, validate_answer
from app.safety.gate import GateResult
from app.safety.messages import TIER1_MESSAGE, care_team_line
from app.safety.rules import Tier
from app.summary.profile import ConfirmedProfile
from app.tools.registry import ToolContext, ToolRegistry

logger = logging.getLogger(__name__)

# The medication agent may use these four tools and no others (CLAUDE.md section 4).
MEDICATION_TOOLS = (
    "get_confirmed_medicines",
    "search_patient_document",
    "search_fda_label",
    "lookup_rxnorm",
)
MAX_ATTEMPTS = 2  # the first answer, and one retry that tells the model what failed
RECENT_TURNS = 4  # how much of the conversation the router may read
RECURSION_LIMIT = 60  # LangGraph's own safety stop; the real limits are in Settings

NO_SOURCES_YET = (
    "(No sources yet. Use the search tools: passages come back labeled D1, D2, ... "
    "and drug labels come back labeled L1, L2, ...)"
)
SCHEDULE_REPLY = (
    "Your reminder times are on your Schedule page. You can also download a calendar file there."
)
OUT_OF_SCOPE_REPLY = (
    "I can help with your discharge papers, your medicines, and your follow-up care. "
    "For anything else, please ask your care team or your pharmacist."
)


class Route(BaseModel):
    """What the router (a small, fast model) decides. It never answers the patient."""

    route: Literal["MEDICINE", "SCHEDULE", "OUT_OF_SCOPE"]
    rewritten_question: str
    focus_medicine: str | None = None


class Citation(BaseModel):
    id: str  # such as "D1"
    kind: Literal["paper", "label"]
    page: int | None = None
    label: str  # the words the tag shows: "From your papers, page 1"


class QuestionResult(BaseModel):
    """Everything the endpoint needs. Only `reply` and `followups` hold patient-facing text."""

    reply: str
    followups: list[str]
    citations: list[Citation]
    outcome: Literal["emergency", "answered", "redirect", "out_of_scope", "fallback"]
    tier: int
    decided_by: str
    task: str
    focus_medicine: str | None
    tool_names: list[str]
    failed_checks: list[str]
    attempts: int
    retrieval_mode: str
    fallback_reason: str | None
    gate_ms: int
    total_ms: int
    # Class name only (never the message, which can hold patient text) of the failed model call.
    fallback_detail: str | None = None


class QuestionState(TypedDict, total=False):
    question: str
    started: float
    gate: GateResult
    gate_ms: int
    tier: Tier
    route: str
    agent_question: str
    focus_medicine: str | None
    messages: list[dict[str, Any]]
    last_reply: LLMResponse
    tool_names: list[str]
    sources: SourceBook
    attempts: int
    failed_checks: list[str]
    validation: ValidationResult
    stop: str | None  # why the loop ended early: timeout, tool_limit or model_error
    fallback_detail: str | None  # the error class name behind a model_error
    outcome: str
    fallback_reason: str | None
    reply: str
    followups: list[str]
    cited: list[str]


@dataclass(frozen=True)
class QuestionDeps:
    """Everything the graph needs from outside, so tests can replace each part."""

    llm: LLM
    settings: Settings
    profile: ConfirmedProfile
    profile_text: str
    answer_template: str
    router_prompt: str
    registry: ToolRegistry  # already narrowed to the medication agent's tools
    tools: ToolContext  # the patient is fixed here, by the server
    gate: Callable[[str], GateResult]
    recall: Recall
    clock: Callable[[], float] = time.monotonic


def _defang(text: str) -> str:
    """Swap every angle bracket for its fullwidth look-alike, as the safety classifier does.

    Nothing typed by the patient, written by the router, said earlier in the conversation or
    carried in the profile can then open or close a tag, or forge our <app_note>. The fullwidth
    signs read the same to a person and to the model, so "temperature > 101" keeps its meaning.
    """
    return text.replace("<", "＜").replace(">", "＞")


def _care_contact(profile: ConfirmedProfile) -> ExtractedContact | None:
    """The care team contact to lead with: one with a phone, and not the pharmacist if possible."""
    with_phone = [contact for contact in profile.care_team if contact.phone]
    for contact in with_phone:
        if "pharmac" not in contact.name.casefold():
            return contact
    return with_phone[0] if with_phone else None


def _fallback_reply(profile: ConfirmedProfile, tier: Tier) -> str:
    """The safe fallback. A Tier 2 patient is also told, first, who on their care team to call."""
    text = fallback_message(profile)
    if tier != Tier.CARE_TEAM:
        return text
    contact = _care_contact(profile)
    if contact is None:
        return f"{care_team_line(None, None)} {text}"
    return f"{care_team_line(contact.name, contact.phone, contact.hours)} {text}"


def known_medicine(profile: ConfirmedProfile, name: str | None) -> str | None:
    """The profile's own name for a medicine the router named, or None if it is not theirs."""
    if not name:
        return None
    wanted = name.strip().casefold()
    for medicine in profile.medicines:
        if wanted in (n.casefold() for n in (medicine.name_as_written, *medicine.other_names)):
            return medicine.name_as_written
    return None


def _router_message(profile: ConfirmedProfile, question: str, recall: Recall) -> str:
    medicines = _defang(
        "\n".join("- " + ", ".join([m.name_as_written, *m.other_names]) for m in profile.medicines)
    )
    recent = "\n".join(
        f"Patient: {turn.question}\nAfterCare: {turn.answer}"
        for turn in recall.turns[-RECENT_TURNS:]
    )
    return (
        f"<medicines>\n{medicines or '(none)'}\n</medicines>\n"
        f"<recent_conversation>\n{_defang(recent) or '(none)'}\n</recent_conversation>\n"
        f"<question>\n{_defang(question)}\n</question>"
    )


def _first_message(question: str, tier: Tier) -> str:
    # The note sits in a tag because every angle bracket in the question is swapped out, so the
    # patient cannot type a note of their own that looks like ours.
    return (
        f"{_defang(question)}\n\n"
        "<app_note>App note, not from the patient: the app's safety check rated this message "
        f"TIER {int(tier)}. Your own safety check can only raise that, never lower it. "
        "Use the search tools to find your sources before you answer.</app_note>"
    )


def build_question_graph(deps: QuestionDeps):
    settings = deps.settings

    def safety_gate(state: QuestionState) -> dict[str, Any]:
        begun = deps.clock()
        gate = deps.gate(state["question"])
        return {"gate": gate, "tier": gate.tier, "gate_ms": int((deps.clock() - begun) * 1000)}

    def after_gate(state: QuestionState) -> str:
        return "emergency" if state["tier"] == Tier.EMERGENCY else "load_context"

    def emergency(state: QuestionState) -> dict[str, Any]:
        # The fixed words, with no model and no retrieval (ADR-0030, ADR-0041).
        return {
            "outcome": "emergency",
            "route": "NONE",
            "reply": state["gate"].fixed_reply or TIER1_MESSAGE,
            "followups": [],
            "cited": [],
        }

    def load_context(_state: QuestionState) -> dict[str, Any]:
        # Short-term memory was loaded by the endpoint into deps.recall; start a clean run.
        return {
            "messages": [],
            "tool_names": [],
            "sources": SourceBook(),
            "attempts": 0,
            "failed_checks": [],
            "stop": None,
        }

    def router(state: QuestionState) -> dict[str, Any]:
        question = state["question"]
        try:
            decision = deps.llm.extract(
                model=settings.model_fast,
                system=deps.router_prompt,
                user=_router_message(deps.profile, question, deps.recall),
                schema=Route,
                max_tokens=settings.router_max_tokens,
            )
        except LLMError:
            # Unsure goes to the medication agent, which has its own scope rule (prompt rule 6).
            decision = Route(route="MEDICINE", rewritten_question=question)

        route = decision.route
        if state["tier"] == Tier.CARE_TEAM:
            route = "MEDICINE"  # a symptom always gets the care-team answer

        rewritten = decision.rewritten_question.strip()
        too_long = len(rewritten) > settings.max_question_chars
        if not rewritten or too_long or len(rewritten) > 3 * len(question) + 80:
            rewritten = question  # a rewrite that grew a lot is not a rewrite
        focus = known_medicine(deps.profile, decision.focus_medicine) or deps.recall.focus_medicine
        update: dict[str, Any] = {
            "route": route,
            "agent_question": rewritten,
            "focus_medicine": focus,
        }
        if route == "MEDICINE":
            first = _first_message(rewritten, state["tier"])
            update["messages"] = [{"role": "user", "content": first}]
        return update

    def after_router(state: QuestionState) -> str:
        return {"SCHEDULE": "schedule_reply", "OUT_OF_SCOPE": "out_of_scope_reply"}.get(
            state["route"], "agent"
        )

    def schedule_reply(_state: QuestionState) -> dict[str, Any]:
        return {"outcome": "redirect", "reply": SCHEDULE_REPLY, "followups": [], "cited": []}

    def out_of_scope_reply(_state: QuestionState) -> dict[str, Any]:
        return {
            "outcome": "out_of_scope",
            "reply": OUT_OF_SCOPE_REPLY,
            "followups": [],
            "cited": [],
        }

    def agent(state: QuestionState) -> dict[str, Any]:
        if deps.clock() - state["started"] > settings.agent_timeout_seconds:
            return {"stop": "timeout"}
        system = fill_prompt(
            deps.answer_template,
            patient_profile=_defang(deps.profile_text),
            retrieved_sources=NO_SOURCES_YET,
            user_question=_defang(state["agent_question"]),
        )
        try:
            reply = deps.llm.complete(
                model=settings.model_main,
                system=system,
                messages=state["messages"],
                tools=deps.registry.specs(),
                max_tokens=settings.answer_max_tokens,
            )
        except LLMError as error:
            return {"stop": "model_error", "fallback_detail": type(error).__name__}
        return {"last_reply": reply}

    def after_agent(state: QuestionState) -> str:
        if state.get("stop"):
            return "fallback"
        return "tools" if state["last_reply"].tool_calls else "validators"

    def run_tool(name: str, raw_input: dict[str, Any]) -> dict[str, Any]:
        try:
            return deps.registry.run(name, raw_input, deps.tools)
        except Exception as error:  # noqa: BLE001  (a broken tool must not end the conversation)
            logger.error("tool %s failed: %s", name, type(error).__name__)
            return {"ok": False, "error": "That tool did not work. Answer without it."}

    def tools(state: QuestionState) -> dict[str, Any]:
        reply = state["last_reply"]
        names = list(state["tool_names"])
        if len(names) + len(reply.tool_calls) > settings.max_tool_calls:
            return {"stop": "tool_limit"}
        sources = state["sources"]
        results: list[dict[str, Any]] = []
        for call in reply.tool_calls:
            names.append(call.name)
            outcome = sources.add_tool_result(call.name, run_tool(call.name, call.input))
            block: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": json.dumps(outcome),
            }
            if not outcome.get("ok"):
                block["is_error"] = True
            results.append(block)
        messages = [
            *state["messages"],
            {"role": "assistant", "content": reply.content},
            {"role": "user", "content": results},
        ]
        return {"messages": messages, "tool_names": names}

    def after_tools(state: QuestionState) -> str:
        return "fallback" if state.get("stop") else "agent"

    def validators(state: QuestionState) -> dict[str, Any]:
        raw = state["last_reply"].text
        sources = state["sources"]
        tier = state["tier"]
        if plain_text(parse_answer(raw).visible) == TIER1_MESSAGE:
            tier = Tier.EMERGENCY  # the model's own safety check found one the gate missed
        result = validate_answer(
            raw,
            tier=tier,
            profile=deps.profile,
            retrieved=sources.texts,
            settings=settings,
            evidence=sources.evidence,
        )
        return {
            "validation": result,
            "attempts": state["attempts"] + 1,
            "failed_checks": [*state["failed_checks"], *result.checks],
        }

    def after_validators(state: QuestionState) -> str:
        if state["validation"].passed:
            return "finalize"
        return "retry" if state["attempts"] < MAX_ATTEMPTS else "fallback"

    def retry(state: QuestionState) -> dict[str, Any]:
        messages = [
            *state["messages"],
            {"role": "assistant", "content": state["last_reply"].content},
            {"role": "user", "content": state["validation"].retry_reason()},
        ]
        return {"messages": messages}

    def fallback(state: QuestionState) -> dict[str, Any]:
        return {
            "outcome": "fallback",
            "fallback_reason": state.get("stop") or "validators",
            "fallback_detail": state.get("fallback_detail"),
            "reply": _fallback_reply(deps.profile, state["tier"]),
            "followups": [],
            "cited": [],
        }

    def finalize(state: QuestionState) -> dict[str, Any]:
        parsed = parse_answer(state["last_reply"].text)  # the hidden <analysis> is dropped here
        known = state["sources"].texts
        cited = [cid for cid in dict.fromkeys(cited_ids(parsed.visible)) if cid in known]
        said_911 = plain_text(parsed.visible) == TIER1_MESSAGE
        return {
            "outcome": "emergency" if said_911 else "answered",
            "reply": parsed.visible,
            "followups": [] if said_911 else parsed.followups[:3],
            "cited": cited,
        }

    graph = StateGraph(QuestionState)
    for name, node in (
        ("safety_gate", safety_gate),
        ("emergency", emergency),
        ("load_context", load_context),
        ("router", router),
        ("schedule_reply", schedule_reply),
        ("out_of_scope_reply", out_of_scope_reply),
        ("agent", agent),
        ("tools", tools),
        ("validators", validators),
        ("retry", retry),
        ("fallback", fallback),
        ("finalize", finalize),
    ):
        graph.add_node(name, node)

    graph.add_edge(START, "safety_gate")
    graph.add_conditional_edges(
        "safety_gate", after_gate, {"emergency": "emergency", "load_context": "load_context"}
    )
    graph.add_edge("emergency", END)
    graph.add_edge("load_context", "router")
    graph.add_conditional_edges(
        "router",
        after_router,
        {
            "agent": "agent",
            "schedule_reply": "schedule_reply",
            "out_of_scope_reply": "out_of_scope_reply",
        },
    )
    graph.add_edge("schedule_reply", END)
    graph.add_edge("out_of_scope_reply", END)
    graph.add_conditional_edges(
        "agent", after_agent, {"tools": "tools", "validators": "validators", "fallback": "fallback"}
    )
    graph.add_conditional_edges("tools", after_tools, {"agent": "agent", "fallback": "fallback"})
    graph.add_conditional_edges(
        "validators",
        after_validators,
        {"finalize": "finalize", "retry": "retry", "fallback": "fallback"},
    )
    graph.add_edge("retry", "agent")
    graph.add_edge("finalize", END)
    graph.add_edge("fallback", END)
    return graph.compile()


def _where(error: BaseException) -> str:
    """Where an error happened, without its message: messages can echo patient text."""
    frames = traceback.extract_tb(error.__traceback__)
    if not frames:
        return "unknown"
    last = frames[-1]
    return f"{last.filename.rsplit('/', 1)[-1]}:{last.lineno} in {last.name}"


def _citations(sources: SourceBook, cited: list[str]) -> list[Citation]:
    found: list[Citation] = []
    for cid in cited:
        meta = sources.meta.get(cid)
        if meta is None:
            continue
        if meta["kind"] == PAPERS:
            label = f"From your papers, page {meta['page']}"
            found.append(Citation(id=cid, kind="paper", page=meta["page"], label=label))
        else:
            found.append(Citation(id=cid, kind="label", label="From the drug label"))
    return found


def _retrieval_mode(deps: QuestionDeps) -> str:
    return str(getattr(deps.tools.search, "last_mode", ""))


def _result(deps: QuestionDeps, state: QuestionState, started: float) -> QuestionResult:
    gate = state.get("gate")
    sources = state.get("sources") or SourceBook()
    return QuestionResult(
        reply=state["reply"],
        followups=state.get("followups", []),
        citations=_citations(sources, state.get("cited", [])),
        outcome=state["outcome"],
        tier=int(state["tier"]),
        decided_by=gate.decided_by if gate else "",
        task=state.get("route", "NONE"),
        focus_medicine=state.get("focus_medicine"),
        tool_names=state.get("tool_names", []),
        failed_checks=state.get("failed_checks", []),
        attempts=state.get("attempts", 0),
        retrieval_mode=_retrieval_mode(deps),
        fallback_reason=state.get("fallback_reason"),
        fallback_detail=state.get("fallback_detail"),
        gate_ms=state.get("gate_ms", 0),
        total_ms=int((deps.clock() - started) * 1000),
    )


def run_question(deps: QuestionDeps, question: str) -> QuestionResult:
    """Run the question graph once. Any unexpected error ends in the safe fallback message."""
    graph = build_question_graph(deps)
    started = deps.clock()
    try:
        state = graph.invoke(
            {"question": question, "started": started}, {"recursion_limit": RECURSION_LIMIT}
        )
    except Exception as error:  # noqa: BLE001  (safety path: any failure means the safe fallback)
        # The type and the place only: an exception's message can hold patient text (ADR-0031).
        logger.error("question graph failed: %s at %s", type(error).__name__, _where(error))
        state = {
            "outcome": "fallback",
            "fallback_reason": "error",
            "reply": _fallback_reply(deps.profile, Tier.CARE_TEAM),
            "tier": Tier.CARE_TEAM,
        }
    return _result(deps, state, started)
