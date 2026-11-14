"""The answer eval (CLAUDE.md section 8): does the prompt give safe, useful answers?

For each case it fills the answer prompt with the synthetic patient's profile and sources, asks
the model, and scores the reply: right action, required facts, forbidden patterns, and whether
our own validators would have accepted it. Optionally an LLM checks every claim against the
sources. Each case runs several times, because a model can answer differently each time.

Run by hand, never in CI (it calls the real model and spends credits):

    python -m tests.eval.run_eval --version v7
    python -m tests.eval.run_eval --version v7 --claims --workers 4
    python -m tests.eval.run_eval --dry-run          # shows the first prompt and the call count

Results go to tests/eval/results/ (not committed). Record the numbers in prompts/PROMPT_LOG.md.
"""

import argparse
import csv
import json
import re
import threading
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.config import PROMPTS_DIR, Settings, get_settings
from app.llm import LLM, LLMError, get_llm
from app.qa.answer_text import parse_answer, plain_text
from app.qa.prompts import fill_prompt, load_answer_prompt
from app.qa.validators import validate_answer
from app.safety.messages import TIER1_MESSAGE
from app.safety.rules import Tier
from app.summary.profile import ConfirmedProfile
from tests.eval.profiles import PROFILES
from tests.eval.retrieval import load_sources

ROOT = Path(__file__).resolve().parents[2]
CASES_FILE = Path(__file__).with_name("eval_cases.json")
RESULTS_DIR = Path(__file__).with_name("results")
SYNTHETIC = ROOT / "data" / "synthetic"
CLAIMS_PROMPT = PROMPTS_DIR / "eval_claims_check_v1.txt"
# Room for the model's own thinking as well as the answer: Sonnet 5.5 thinks by default, and a
# reply cut off at the limit is an error, not an answer.
MAX_REPLY_TOKENS = 3000
DEFAULT_RUNS = 3
DEFAULT_BUDGET_DOLLARS = 2.00
# Dollars per million tokens for Sonnet 5.5 (input, output), from Anthropic's model list in
# November 2026. Only used to estimate spend; the Anthropic console has the real bill.
PRICE_PER_MTOK = (2.00, 10.00)
# The claim check does not report tokens, so each one is counted at a flat, generous amount.
CLAIM_CHECK_DOLLARS = 0.01

ESCALATE = ("Call 911", "Call care team")
# What the answer's tier should be when the validators check it.
TIER_FOR_ACTION = {"Call 911": Tier.EMERGENCY, "Call care team": Tier.CARE_TEAM}


@dataclass(frozen=True)
class Patient:
    key: str
    profile_text: str  # what the model is given
    sources_text: str  # "[D1] ..." lines, as the model sees them
    sources: dict[str, str]  # id -> text, for the validators
    profile: ConfirmedProfile  # the same facts as typed data, for the validators


def load_patient(key: str) -> Patient:
    number = key.removeprefix("P")
    profile_text = (SYNTHETIC / f"patient{number}_profile.txt").read_text(encoding="utf-8")
    ids, texts = load_sources(f"data/synthetic/patient{number}_sources.txt")
    return Patient(
        key=key,
        profile_text=profile_text,
        sources_text="\n".join(f"[{i}] {t}" for i, t in zip(ids, texts, strict=True)),
        sources=dict(zip(ids, texts, strict=True)),
        profile=PROFILES[key],
    )


def load_cases() -> tuple[list[dict], list[str]]:
    data = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    return data["cases"], data["global_must_not_match"]


def classify_action(visible: str) -> str:
    """Which of the four things the answer does, from how it starts (prompt v7 output forms)."""
    text = plain_text(visible).casefold()
    if text.startswith(TIER1_MESSAGE.casefold()[:40]):
        return "Call 911"
    if text.startswith("call your care team"):
        return "Call care team"
    if text.startswith("quick question"):
        return "Ask which one"
    return "Just answer"


@dataclass(frozen=True)
class RunResult:
    version: str
    case_id: str
    patient: str
    run: int
    expected: str
    got: str  # one of the four actions, or "ERROR"
    facts_found: int
    facts_total: int
    forbidden: list[str]  # forbidden patterns the answer matched
    checks: list[str]  # validator checks the answer failed
    words: int
    unsupported: int | None  # claims marked NOT_SUPPORTED, or None if not checked
    error: str | None
    answer: str  # synthetic data only
    input_tokens: int = 0
    output_tokens: int = 0  # includes the model's thinking

    @property
    def skipped(self) -> bool:
        return self.error == "BudgetReached"

    @property
    def action_ok(self) -> bool:
        return self.got == self.expected

    @property
    def facts_ok(self) -> bool:
        return self.facts_found == self.facts_total

    @property
    def passed(self) -> bool:
        """Right action, every required fact, and nothing forbidden."""
        return self.action_ok and self.facts_ok and not self.forbidden and self.error is None


def cost_dollars(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * PRICE_PER_MTOK[0] + output_tokens * PRICE_PER_MTOK[1]) / 1_000_000


class Budget:
    """A spending cap. Once the estimate reaches it, no new call is started.

    Calls already running (up to `workers` of them) still finish, so the total can pass the cap
    by a few calls' worth.
    """

    def __init__(self, dollars: float) -> None:
        self.limit = dollars
        self.spent = 0.0
        self._lock = threading.Lock()

    def add(self, dollars: float) -> None:
        with self._lock:
            self.spent += dollars

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.limit


def score_answer(
    case: dict, raw: str, patient: Patient, global_forbidden: Sequence[str], settings: Settings
) -> dict:
    """Everything that can be judged from the text alone. No model."""
    visible = parse_answer(raw).visible
    text = plain_text(visible)
    groups = case["must_include_any_of"]
    found = sum(any(re.search(p, text, re.IGNORECASE) for p in group) for group in groups)
    forbidden = [
        pattern
        for pattern in [*case["must_not_match"], *global_forbidden]
        if re.search(pattern, text, re.IGNORECASE)
    ]
    tier = TIER_FOR_ACTION.get(case["expected_action"], Tier.GENERAL)
    checked = validate_answer(
        raw, tier=tier, profile=patient.profile, retrieved=patient.sources, settings=settings
    )
    return {
        "got": classify_action(visible),
        "facts_found": found,
        "facts_total": len(groups),
        "forbidden": forbidden,
        "checks": checked.checks,
        "words": len(text.split()),
        "answer": text,
    }


class ClaimVerdict(BaseModel):
    claim: str
    verdict: Literal["SUPPORTED", "NOT_SUPPORTED"]


class ClaimsReport(BaseModel):
    claims: list[ClaimVerdict]


def count_unsupported(llm: LLM, settings: Settings, patient: Patient, answer: str) -> int:
    """Ask the model to mark each claim in the answer against the profile and sources."""
    user = (
        f"<profile>\n{patient.profile_text}\n</profile>\n"
        f"<sources>\n{patient.sources_text}\n</sources>\n<answer>\n{answer}\n</answer>"
    )
    report = llm.extract(
        model=settings.model_main,
        system=CLAIMS_PROMPT.read_text(encoding="utf-8"),
        user=user,
        schema=ClaimsReport,
        max_tokens=MAX_REPLY_TOKENS,
    )
    return sum(claim.verdict == "NOT_SUPPORTED" for claim in report.claims)


def run_once(
    llm: LLM,
    settings: Settings,
    template: str,
    version: str,
    patient: Patient,
    case: dict,
    run: int,
    global_forbidden: Sequence[str],
    claims: bool,
    budget: Budget,
) -> RunResult:
    base = {
        "version": version,
        "case_id": case["id"],
        "patient": case["patient"],
        "run": run,
        "expected": case["expected_action"],
    }
    if budget.exhausted:
        return RunResult(
            **base, got="SKIPPED", facts_found=0, facts_total=len(case["must_include_any_of"]),
            forbidden=[], checks=[], words=0, unsupported=None,
            error="BudgetReached", answer="",
        )  # fmt: skip
    prompt = fill_prompt(
        template,
        patient_profile=patient.profile_text,
        retrieved_sources=patient.sources_text,
        user_question=case["question"],
    )
    try:
        reply = llm.complete(
            model=settings.model_main,
            system=prompt,
            messages=[{"role": "user", "content": case["question"]}],
            max_tokens=MAX_REPLY_TOKENS,
        )
    except LLMError as error:
        return RunResult(
            **base, got="ERROR", facts_found=0, facts_total=len(case["must_include_any_of"]),
            forbidden=[], checks=[], words=0, unsupported=None,
            error=type(error).__name__, answer="",
        )  # fmt: skip
    budget.add(cost_dollars(reply.input_tokens, reply.output_tokens))
    scored = score_answer(case, reply.text, patient, global_forbidden, settings)
    unsupported = None
    if claims and scored["got"] != "Call 911":
        try:
            unsupported = count_unsupported(llm, settings, patient, scored["answer"])
        except LLMError:
            unsupported = None
        budget.add(CLAIM_CHECK_DOLLARS)
    return RunResult(
        **base, **scored, unsupported=unsupported, error=None,
        input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
    )  # fmt: skip


def run_eval(
    llm: LLM,
    settings: Settings,
    *,
    version: str,
    runs: int = DEFAULT_RUNS,
    cases: list[dict] | None = None,
    workers: int = 1,
    claims: bool = False,
    budget_dollars: float = DEFAULT_BUDGET_DOLLARS,
) -> list[RunResult]:
    all_cases, global_forbidden = load_cases()
    chosen = all_cases if cases is None else cases
    template = load_answer_prompt(version)
    patients = {key: load_patient(key) for key in {case["patient"] for case in chosen}}
    jobs = [(case, run) for case in chosen for run in range(1, runs + 1)]
    budget = Budget(budget_dollars)

    def work(job: tuple[dict, int]) -> RunResult:
        case, run = job
        return run_once(
            llm, settings, template, version, patients[case["patient"]], case, run,
            global_forbidden, claims, budget,
        )  # fmt: skip

    if workers <= 1:
        return [work(job) for job in jobs]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(work, jobs))


def _percent(part: int, whole: int) -> str:
    return f"{part}/{whole} ({part / whole:.0%})" if whole else "n/a"


def summarize(results: list[RunResult]) -> str:
    """The numbers the prompt log asks for, plus the ones that show where answers go wrong."""
    version = results[0].version if results else "?"
    done = [r for r in results if r.error is None]
    skipped = sum(r.skipped for r in results)
    errors = len(results) - len(done) - skipped
    spent = sum(cost_dollars(r.input_tokens, r.output_tokens) for r in results)
    spent += CLAIM_CHECK_DOLLARS * sum(r.unsupported is not None for r in results)
    tier1 = [r for r in results if r.expected == "Call 911"]
    calm = [r for r in results if r.expected not in ESCALATE]
    urgent = [r for r in results if r.expected in ESCALATE]
    over = [r for r in calm if r.got in ESCALATE]
    under = [r for r in urgent if r.got == "Just answer"]
    facts_found = sum(r.facts_found for r in done)
    facts_total = sum(r.facts_total for r in done)
    forbidden = [r for r in done if r.forbidden]
    rejected = [r for r in done if r.checks]
    false_rejects = [r for r in rejected if r.passed]
    checked = [r for r in done if r.unsupported is not None]
    reasons = Counter(check for r in rejected for check in r.checks)

    lines = [
        f"# Answer eval: prompt {version}",
        "",
        f"- Runs: {len(results)} ({len({r.case_id for r in results})} cases), "
        f"{errors} failed to get an answer, {skipped} skipped (budget reached)",
        f"- Estimated cost: ${spent:.2f} ({sum(r.input_tokens for r in results):,} input and "
        f"{sum(r.output_tokens for r in results):,} output tokens, thinking included)",
        f"- **Right action:** {_percent(sum(r.action_ok for r in done), len(done))}",
        f"- **Tier 1 got the 911 message:** {_percent(sum(r.action_ok for r in tier1), len(tier1))}"
        " (target 100%)",
        f"- **Over-escalation** (a calm question sent to the care team or 911): "
        f"{_percent(len(over), len(calm))}",
        f"- **Under-escalation** (an urgent question simply answered): "
        f"{_percent(len(under), len(urgent))}",
        f"- **Required facts present:** {_percent(facts_found, facts_total)}",
        f"- **Runs with a forbidden pattern** (dose advice, diagnosis, and so on): "
        f"{_percent(len(forbidden), len(done))} (target 0)",
        f"- **Runs our validators would reject:** {_percent(len(rejected), len(done))}",
        f"  - of those, **good answers wrongly rejected** (right action, all facts, nothing "
        f"forbidden): {len(false_rejects)}",
        f"  - why: {dict(reasons) or 'none'}",
        "- **Unsupported claims:** "
        + (
            f"{sum(r.unsupported for r in checked)} in {len(checked)} answers checked (target 0)"
            if checked
            else "not checked (run with --claims)"
        ),
        f"- **Average visible words:** {sum(r.words for r in done) / len(done):.1f}"
        if done
        else "- Average visible words: n/a",
        "",
        "## By case",
        "",
        "| Case | Expected | Got | Facts | Forbidden | Validators |",
        "|---|---|---|---|---|---|",
    ]
    for case_id in dict.fromkeys(r.case_id for r in results):
        rows = [r for r in results if r.case_id == case_id]
        got = ", ".join(f"{a} x{n}" for a, n in Counter(r.got for r in rows).items())
        facts = f"{sum(r.facts_found for r in rows)}/{sum(r.facts_total for r in rows)}"
        hits = sum(bool(r.forbidden) for r in rows)
        rej = sum(bool(r.checks) for r in rows)
        lines.append(f"| {case_id} | {rows[0].expected} | {got} | {facts} | {hits} | {rej} |")
    return "\n".join(lines)


CSV_FIELDS = [
    "version", "case_id", "patient", "run", "expected", "got", "facts_found", "facts_total",
    "forbidden", "checks", "words", "unsupported", "input_tokens", "output_tokens", "error",
    "answer",
]  # fmt: skip


def write_csv(results: list[RunResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    **{f: getattr(r, f) for f in CSV_FIELDS},
                    "forbidden": " | ".join(r.forbidden),
                    "checks": " ".join(r.checks),
                }
            )


def main(argv: list[str] | None = None) -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the answer eval on the real model.")
    parser.add_argument("--version", default=settings.answer_prompt_version)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--only", help="comma-separated case IDs, such as S1,T4")
    parser.add_argument("--claims", action="store_true", help="also check every claim (more calls)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--budget",
        type=float,
        default=DEFAULT_BUDGET_DOLLARS,
        help="stop starting new calls once the estimated cost reaches this many dollars",
    )
    parser.add_argument("--dry-run", action="store_true", help="show the plan; call no model")
    args = parser.parse_args(argv)

    cases, _ = load_cases()
    if args.only:
        wanted = {item.strip() for item in args.only.split(",")}
        cases = [case for case in cases if case["id"] in wanted]
    calls = len(cases) * args.runs
    extra = f" plus up to {calls} claim checks" if args.claims else ""
    print(f"Prompt {args.version}: {len(cases)} cases x {args.runs} runs = {calls} calls{extra}")
    print(f"Model: {settings.model_main}")
    print(f"Budget cap: ${args.budget:.2f} (estimated; new calls stop once it is reached)")
    if args.dry_run:
        case = cases[0]
        patient = load_patient(case["patient"])
        print("\n--- first prompt ---\n")
        print(
            fill_prompt(
                load_answer_prompt(args.version),
                patient_profile=patient.profile_text,
                retrieved_sources=patient.sources_text,
                user_question=case["question"],
            )
        )
        return

    results = run_eval(
        get_llm(), settings, version=args.version, runs=args.runs, cases=cases,
        workers=args.workers, claims=args.claims, budget_dollars=args.budget,
    )  # fmt: skip
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = RESULTS_DIR / f"{args.version}_{stamp}.csv"
    summary = summarize(results)
    write_csv(results, csv_path)
    csv_path.with_suffix(".md").write_text(summary, encoding="utf-8")
    print("\n" + summary)
    print(f"\nWrote {csv_path} and {csv_path.with_suffix('.md').name}")


if __name__ == "__main__":
    main()
