"""The safety gate: fixed code that runs before any agent (CLAUDE.md section 5, ADR-0005).

The final tier is the more severe of the keyword rules and the classifier. A possible emergency
returns the fixed 911 text and stops: the classifier is not even called, because nothing it said
could lower the tier.
"""

from typing import Literal

from pydantic import BaseModel

from app.config import Settings
from app.llm import LLM
from app.safety.classifier import classify
from app.safety.context import PatientSafetyContext
from app.safety.messages import TIER1_MESSAGE
from app.safety.rules import Tier, apply_rules


class GateResult(BaseModel):
    """What the gate decided. Holds no patient text, so it is safe to log."""

    tier: Tier
    decided_by: Literal["rules", "classifier", "nothing_to_check"]
    rule_hits: list[str]
    classifier_runs: list[Tier]
    classifier_failures: int
    fixed_reply: str | None  # the fixed 911 text for Tier 1, otherwise None


def run_gate(
    question: str, context: PatientSafetyContext, *, llm: LLM, settings: Settings
) -> GateResult:
    if not question.strip():
        return GateResult(
            tier=Tier.GENERAL,
            decided_by="nothing_to_check",
            rule_hits=[],
            classifier_runs=[],
            classifier_failures=0,
            fixed_reply=None,
        )

    rules = apply_rules(question, context)
    if rules.tier == Tier.EMERGENCY:
        return GateResult(
            tier=Tier.EMERGENCY,
            decided_by="rules",
            rule_hits=rules.hits,
            classifier_runs=[],
            classifier_failures=0,
            fixed_reply=TIER1_MESSAGE,
        )

    verdict = classify(llm, settings, question, context)
    tier = Tier(min(rules.tier, verdict.tier))
    return GateResult(
        tier=tier,
        decided_by="rules" if rules.tier < verdict.tier else "classifier",
        rule_hits=rules.hits,
        classifier_runs=verdict.runs,
        classifier_failures=verdict.failed,
        fixed_reply=TIER1_MESSAGE if tier == Tier.EMERGENCY else None,
    )
