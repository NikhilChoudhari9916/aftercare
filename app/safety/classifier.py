"""The small-model half of the safety gate: three readings, the most severe wins (ADR-0005).

Every way this can go wrong lands on Tier 2, never Tier 3: a run that errors, times out, or
answers in a way we cannot read counts as Tier 2.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, wait

from pydantic import BaseModel

from app.config import Settings
from app.llm import LLM
from app.prompts import load_prompt
from app.safety.context import PatientSafetyContext
from app.safety.rules import Tier

CLASSIFIER_PROMPT = "safety_classifier_system_prompt_v1.txt"
MAX_REPLY_TOKENS = (
    200  # the reply is one line, but a few extra words must not be cut off and discarded
)
NO_WARNING_SIGNS = "(the papers list none)"

logger = logging.getLogger(__name__)
_TIER_WORDS = re.compile(r"tier\s*([123])", re.IGNORECASE)


class ClassifierVerdict(BaseModel):
    tier: Tier
    runs: list[Tier]  # the tier each run gave; a failed run shows as Tier 2
    failed: int  # how many runs errored, timed out, or could not be read


def parse_tier(reply: str) -> Tier | None:
    """The most serious tier named in the reply, or None if it names none."""
    found = [int(number) for number in _TIER_WORDS.findall(reply)]
    return Tier(min(found)) if found else None


def _system_prompt(context: PatientSafetyContext) -> str:
    signs = "\n".join(
        f"- {'CALL 911' if sign.tier == 'CALL_911' else 'CALL CARE TEAM'}: {sign.text}"
        for sign in context.warning_signs
    )
    return load_prompt(CLASSIFIER_PROMPT).replace(
        "{patient_warning_signs}", signs or NO_WARNING_SIGNS
    )


def _user_message(question: str) -> str:
    # Angle brackets are swapped so the patient's text cannot close the <question> tag itself.
    safe = question.replace("<", "＜").replace(">", "＞")
    return f"<question>\n{safe}\n</question>"


def _one_run(llm: LLM, settings: Settings, system: str, user: str) -> Tier:
    reply = llm.complete(
        model=settings.model_fast,
        system=system,
        messages=[{"role": "user", "content": user}],
        max_tokens=MAX_REPLY_TOKENS,
    )
    tier = parse_tier(reply.text)
    if tier is None:
        raise ValueError("the classifier reply named no tier")
    return tier


def classify(
    llm: LLM, settings: Settings, question: str, context: PatientSafetyContext
) -> ClassifierVerdict:
    system, user = _system_prompt(context), _user_message(question)
    runs = settings.classifier_runs
    pool = ThreadPoolExecutor(max_workers=runs)
    futures = [pool.submit(_one_run, llm, settings, system, user) for _ in range(runs)]
    wait(futures, timeout=settings.classifier_timeout_seconds)
    pool.shutdown(wait=False, cancel_futures=True)  # do not hold the patient for a stuck call

    tiers: list[Tier] = []
    failed = 0
    for future in futures:
        try:
            if not future.done():
                raise TimeoutError
            tiers.append(future.result())
        except Exception as error:  # noqa: BLE001  (safety path: any failure means Tier 2)
            failed += 1
            tiers.append(Tier.CARE_TEAM)
            logger.warning("safety classifier run failed: %s", type(error).__name__)
    return ClassifierVerdict(tier=Tier(min(tiers)), runs=tiers, failed=failed)
