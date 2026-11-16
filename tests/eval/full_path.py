"""The full-path eval (handoff C2): each question goes through the real question graph.

`run_eval.py` shows the model the prompt with the sources already filled in, and lets the model
write the 911 text itself. This sends the same questions through what users reach: the safety
gate, the router, the medication agent with its four tools, search over the patient's chunks,
the validators, and the fixed fallback. It builds no interface of its own: it fills in
`QuestionDeps` and calls `run_question`, exactly as `app/qa/routes.py` does.

What stands in for the app's data (synthetic only, in a throwaway database):
- The patient's confirmed profile is `tests/eval/profiles.py`.
- Search chunks are the `[D#]` lines of `data/synthetic/patientN_sources.txt`, stored as Chunk rows.
- openFDA is replaced by the `[L#]` lines of the same file, so no internet is needed.
- RxNorm is left out (`None`): the tool answers "not available" and the agent goes on without it.

Not paid for until you run it: `--dry-run` calls no model (see `dry_run_report`).
"""

import re
import tempfile
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.agents.question_graph import (
    MEDICATION_TOOLS,
    QuestionDeps,
    QuestionResult,
    run_question,
)
from app.config import Settings
from app.enrichment.openfda import LabelText
from app.llm import LLM, LLMError
from app.memory.session import Recall
from app.models import (
    Chunk,
    ChunkSource,
    Document,
    Patient,
    ProfileItem,
    ProfileStatus,
    ProfileVersion,
    User,
)
from app.prompts import load_prompt
from app.qa.factory import build_retriever
from app.qa.profile_text import render_profile_text
from app.qa.prompts import load_answer_prompt
from app.qa.retriever import Retriever
from app.safety.context import safety_context
from app.safety.gate import GateResult, run_gate
from app.safety.rules import apply_rules
from app.summary.profile import ConfirmedProfile, load_confirmed_profile
from app.tools import ToolContext, default_registry
from tests.eval.profiles import PROFILES
from tests.eval.retrieval import load_sources
from tests.eval.run_eval import (
    Budget,
    RunResult,
    classify_action,
    count_unsupported,
    load_patient,
    score_answer,
)
from tests.eval.run_eval import (
    Patient as EvalPatient,
)

# The graph does not report tokens, so a question is counted at a flat, generous amount for the
# budget cap: about 3 safety runs, a router call and 2 to 4 agent turns of about 4,000 tokens.
QUESTION_DOLLARS = 0.04
# One question: 3 safety runs + 1 router + usually 2 agent turns (search, then answer).
TYPICAL_MODEL_CALLS = 6
TOP_K = 4

# What `got` says when the app did something other than answer. None of these is an expected
# action, so each shows up as a miss in the summary instead of hiding as "Just answer".
FALLBACK = "Fallback"
REDIRECT = "Redirect"
OUT_OF_SCOPE = "Out of scope"


class SourceLabels:
    """Stands in for openFDA: hands back the `[L#]` line whose text names the medicine."""

    def __init__(self, label_lines: dict[str, str]) -> None:
        self._lines = label_lines

    def get_label(self, names: list[str]) -> LabelText:
        for line in self._lines.values():
            lowered = line.casefold()
            if any(name.casefold() in lowered for name in names):
                return LabelText(found=True, medicine=names[0], warnings=line)
        return LabelText(found=False, medicine=names[0] if names else "")


@dataclass(frozen=True)
class World:
    """Throwaway database holding the synthetic patients, and the settings that point at it."""

    engine: Engine
    patient_ids: dict[str, str]  # "P1" -> the patient's database ID
    labels: dict[str, SourceLabels]
    settings: Settings


def _section_and_page(head: str) -> tuple[str, int]:
    """'Discharge instructions, page 2, Incision care' -> ('Incision care', 2)."""
    page = re.search(r"page (\d+)", head)
    section = head.rsplit(", ", 1)[-1]
    return section, int(page.group(1)) if page else 1


def _add_patient(db: Session, key: str) -> tuple[str, SourceLabels]:
    profile = PROFILES[key]
    user = User(google_sub=f"eval-{key}", email=f"{key}@example.com", display_name=key)
    db.add(user)
    db.commit()
    patient = Patient(owner_user_id=user.id)
    db.add(patient)
    db.commit()
    document = Document(patient_id=patient.id, page_count=1)
    db.add(document)
    db.commit()
    version = ProfileVersion(
        patient_id=patient.id,
        document_id=document.id,
        version=1,
        status=ProfileStatus.CONFIRMED,
        discharge_date=profile.discharge_date.isoformat() if profile.discharge_date else None,
    )
    db.add(version)
    db.commit()
    sections = {
        "medicines": profile.medicines,
        "warning_signs": profile.warning_signs,
        "follow_ups": profile.follow_ups,
        "care_team": profile.care_team,
        "diet_limits": profile.diet_limits,
    }
    for section, items in sections.items():
        for position, item in enumerate(items):
            db.add(
                ProfileItem(
                    profile_version_id=version.id,
                    patient_id=patient.id,
                    section=section,
                    position=position,
                    data=item.model_dump_json(),
                    quote_status="verified",
                    confirmed=True,
                )
            )

    ids, texts = load_sources(f"data/synthetic/patient{key.removeprefix('P')}_sources.txt")
    labels: dict[str, str] = {}
    for source_id, text in zip(ids, texts, strict=True):
        if source_id.startswith("L"):
            labels[source_id] = text
            continue
        head, _, body = text.partition(": ")
        section, page = _section_and_page(head)
        position = int(source_id.removeprefix("D"))
        db.add(
            Chunk(
                patient_id=patient.id,
                profile_version_id=version.id,
                source=ChunkSource.DOCUMENT,
                ref=source_id,  # the eval cases' D numbers stay the ones the model cites
                position=position,
                page=page,
                section=section,
                text=body or text,
            )
        )
    db.commit()
    return patient.id, SourceLabels(labels)


def build_world(keys: Sequence[str], settings: Settings, directory: Path) -> World:
    """One file-backed SQLite database, so each worker thread can open its own session."""
    engine = create_engine(
        f"sqlite:///{directory / 'full_path.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    patient_ids: dict[str, str] = {}
    labels: dict[str, SourceLabels] = {}
    with Session(engine) as db:
        for key in keys:
            patient_ids[key], labels[key] = _add_patient(db, key)
    # Search indexes go in the throwaway folder, not into the project's storage/.
    return World(
        engine, patient_ids, labels, settings.model_copy(update={"storage_dir": directory})
    )


def _deps(
    world: World,
    db: Session,
    llm: LLM,
    key: str,
    retriever: Retriever,
    on_gate: Callable[[GateResult], None] | None = None,
) -> QuestionDeps | None:
    patient_id = world.patient_ids[key]
    profile = load_confirmed_profile(db, patient_id)
    if profile is None:
        return None
    settings = world.settings
    context = safety_context(profile)

    def gate(text: str) -> GateResult:
        verdict = run_gate(text, context, llm=llm, settings=settings)
        if on_gate is not None:
            on_gate(verdict)  # the eval only watches; the verdict is returned unchanged
        return verdict

    return QuestionDeps(
        llm=llm,
        settings=settings,
        profile=profile,
        profile_text=render_profile_text(profile),
        answer_template=load_answer_prompt(settings.answer_prompt_version),
        router_prompt=load_prompt(f"router_system_prompt_{settings.router_prompt_version}.txt"),
        registry=default_registry().only(MEDICATION_TOOLS),
        tools=ToolContext(
            db=db,
            patient_id=patient_id,
            rxnorm=None,
            openfda=world.labels[key],
            search=retriever,
        ),
        gate=gate,
        recall=Recall(),  # every question is asked fresh, as in the prompt-only eval
    )


def action_taken(result: QuestionResult) -> str:
    """The same four actions as the prompt-only eval, plus what the app did instead."""
    if result.outcome == "emergency":
        return "Call 911"
    if result.outcome == "fallback":
        return FALLBACK
    if result.outcome == "redirect":
        return REDIRECT
    if result.outcome == "out_of_scope":
        return OUT_OF_SCOPE
    return classify_action(result.reply)


def run_once(
    world: World,
    llm: LLM,
    version: str,
    patient: EvalPatient,
    case: dict,
    run: int,
    global_forbidden: Sequence[str],
    claims: bool,
    budget: Budget,
) -> RunResult:
    base = {
        "version": f"{version}+graph",
        "case_id": case["id"],
        "patient": case["patient"],
        "run": run,
        "expected": case["expected_action"],
    }
    total = len(case["must_include_any_of"])
    if budget.exhausted:
        return RunResult(
            **base, got="SKIPPED", facts_found=0, facts_total=total, forbidden=[], checks=[],
            words=0, unsupported=None, error="BudgetReached", answer="",
        )  # fmt: skip
    with Session(world.engine) as db:
        retriever = build_retriever(db, world.settings)
        verdicts: list[GateResult] = []
        deps = _deps(world, db, llm, case["patient"], retriever, verdicts.append)
        if deps is None:
            raise RuntimeError(f"{case['patient']} has no confirmed profile in the eval database")
        result = run_question(deps, case["question"])
    budget.add(QUESTION_DOLLARS)

    scored = score_answer(case, result.reply, patient, global_forbidden, world.settings)
    scored["got"] = action_taken(result)
    scored["checks"] = result.failed_checks  # what the graph's own validators found, as it ran
    unsupported = None
    if claims and scored["got"] not in ("Call 911", FALLBACK, REDIRECT, OUT_OF_SCOPE):
        try:
            unsupported = count_unsupported(llm, world.settings, patient, scored["answer"])
        except LLMError:
            unsupported = None
        budget.add(0.01)
    return RunResult(
        **base, **scored, unsupported=unsupported, error=None,
        gate_tier=result.tier,
        decided_by=result.decided_by,
        classifier_failures=sum(v.classifier_failures for v in verdicts),
        route=result.task,
        tool_names=result.tool_names,
        attempts=result.attempts,
        fallback_reason=result.fallback_reason,
        fallback_detail=result.fallback_detail,
        total_ms=result.total_ms,
    )  # fmt: skip


def run_full_path(
    llm: LLM,
    settings: Settings,
    *,
    version: str,
    cases: list[dict],
    global_forbidden: Sequence[str],
    runs: int,
    workers: int,
    claims: bool,
    budget_dollars: float,
) -> list[RunResult]:
    # The graph reads the answer prompt version from settings, so the flag must reach it there.
    settings = settings.model_copy(update={"answer_prompt_version": version})
    keys = sorted({case["patient"] for case in cases})
    patients = {key: load_patient(key) for key in keys}
    budget = Budget(budget_dollars)
    jobs = [(case, run) for case in cases for run in range(1, runs + 1)]
    with tempfile.TemporaryDirectory(prefix="aftercare-full-path-") as folder:
        world = build_world(keys, settings, Path(folder))
        try:

            def work(job: tuple[dict, int]) -> RunResult:
                case, run = job
                return run_once(
                    world, llm, version, patients[case["patient"]], case, run,
                    global_forbidden, claims, budget,
                )  # fmt: skip

            if workers <= 1:
                return [work(job) for job in jobs]
            with ThreadPoolExecutor(max_workers=workers) as pool:
                return list(pool.map(work, jobs))
        finally:
            world.engine.dispose()  # Windows cannot delete the file while it is open


def dry_run_report(
    cases: list[dict], settings: Settings, runs: int, version: str, claims: bool
) -> str:
    """What a real run would do, found without any model call.

    For each case: the tier the fixed keyword rules give (a Tier 1 never reaches a model) and
    the top passages keyword search returns from this patient's chunks.
    """
    keys = sorted({case["patient"] for case in cases})
    settings = settings.model_copy(update={"answer_prompt_version": version})
    questions = len(cases) * runs
    emergencies = sum(case["expected_action"] == "Call 911" for case in cases) * runs
    model_calls = (questions - emergencies) * TYPICAL_MODEL_CALLS
    lines = [
        f"Full path with prompt {version}: {len(cases)} cases x {runs} runs"
        f" = {questions} questions",
        f"About {model_calls} model calls "
        f"({emergencies} expected emergencies need none: the keyword rules answer them)"
        + (" plus one claim check per answer" if claims else ""),
        "",
        "case   expected         rules tier  top passages (keyword search)",
    ]
    with tempfile.TemporaryDirectory(prefix="aftercare-full-path-") as folder:
        world = build_world(keys, settings, Path(folder))
        try:
            with Session(world.engine) as db:
                retriever = Retriever(db)  # keywords only: the dry run loads no embedding model
                for case in cases:
                    patient_id = world.patient_ids[case["patient"]]
                    profile: ConfirmedProfile | None = load_confirmed_profile(db, patient_id)
                    if profile is None:
                        raise RuntimeError(f"{case['patient']} has no confirmed profile")
                    tier = apply_rules(case["question"], safety_context(profile)).tier
                    found = retriever.search(patient_id, case["question"], TOP_K)
                    refs = " ".join(passage.id for passage in found) or "(nothing)"
                    lines.append(f"{case['id']:7}{case['expected_action']:17}{tier.name:12}{refs}")
        finally:
            world.engine.dispose()  # Windows cannot delete the file while it is open
    return "\n".join(lines)
