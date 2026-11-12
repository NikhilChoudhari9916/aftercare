"""The gate against the project's 31 eval questions (CLAUDE.md section 8).

These run with a fake classifier that always says Tier 3, so what they prove is the floor the
fixed rules give on their own. The real classifier can only raise a tier, never lower one.
"""

import json
from pathlib import Path

import pytest

from app.safety.gate import run_gate
from app.safety.messages import TIER1_MESSAGE
from app.safety.rules import Tier, apply_rules
from tests.auth.helpers import make_settings
from tests.safety.helpers import CONTEXTS, llm_saying

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "eval" / "eval_cases.json").read_text(encoding="utf-8")
)["cases"]
EXPECTED_TIER = {
    "Call 911": Tier.EMERGENCY,
    "Call care team": Tier.CARE_TEAM,
    "Just answer": Tier.GENERAL,
    "Ask which one": Tier.GENERAL,
}
IDS = [case["id"] for case in CASES]


def test_the_eval_file_still_has_all_31_cases_and_a_known_action_for_each():
    assert len(CASES) == 31
    assert {case["expected_action"] for case in CASES} == set(EXPECTED_TIER)


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_the_rules_alone_give_the_expected_tier(case):
    context = CONTEXTS[case["patient"]]()
    assert apply_rules(case["question"], context).tier == EXPECTED_TIER[case["expected_action"]]


def test_tier_1_recall_is_100_percent_and_every_one_gets_the_fixed_911_text():
    emergencies = [case for case in CASES if case["expected_action"] == "Call 911"]
    assert len(emergencies) >= 4

    for case in emergencies:
        context = CONTEXTS[case["patient"]]()
        llm = llm_saying(*["TIER 3"] * 3)  # even a classifier that misses it cannot matter
        result = run_gate(case["question"], context, llm=llm, settings=make_settings())

        assert result.tier == Tier.EMERGENCY, case["id"]
        assert result.fixed_reply == TIER1_MESSAGE, case["id"]
        assert llm.calls == [], case["id"]


def test_no_everyday_question_is_escalated_by_the_rules():
    everyday = [c for c in CASES if c["expected_action"] in ("Just answer", "Ask which one")]
    escalated = [
        case["id"]
        for case in everyday
        if apply_rules(case["question"], CONTEXTS[case["patient"]]()).tier != Tier.GENERAL
    ]
    assert escalated == []
