"""The fixed keyword rules of the safety gate. Plain code: no model, no network.

Rules only raise the tier. They read data/red_flags.yaml (shared by every patient) and the
patient's own confirmed warning signs and medicine names.
"""

import math
import re
import unicodedata
from enum import IntEnum
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.config import RED_FLAGS_FILE
from app.safety.context import PatientSafetyContext, ProfileWarningSign

# How far apart a medicine action and the medicine's name may be ("forgot my xarelto last night").
NAME_REACH = 25


class Tier(IntEnum):
    """A smaller number is more serious, so the most severe tier is min()."""

    EMERGENCY = 1
    CARE_TEAM = 2
    GENERAL = 3


class RulesError(Exception):
    """The rules file is missing or broken. The app should not run without its safety rules."""


class RuleResult(BaseModel):
    tier: Tier
    hits: list[str]  # names of the rules that matched, never the patient's words


class RedFlagRules(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    tier1: dict[str, list[re.Pattern[str]]]
    tier2: dict[str, list[re.Pattern[str]]]
    medicine_action: re.Pattern[str]


def _compile(patterns: object, where: str) -> list[re.Pattern[str]]:
    if not isinstance(patterns, list) or not patterns:
        raise RulesError(f"{where} needs a non-empty list of patterns")
    try:
        return [re.compile(str(pattern), re.IGNORECASE) for pattern in patterns]
    except re.error as error:
        raise RulesError(f"{where} has a pattern that does not compile: {error}") from error


def _group(raw: object, tier: str) -> dict[str, list[re.Pattern[str]]]:
    if not isinstance(raw, dict) or not raw:
        raise RulesError(f"{tier} needs at least one category")
    return {name: _compile(patterns, f"{tier}.{name}") for name, patterns in raw.items()}


@lru_cache
def load_rules(path: Path = RED_FLAGS_FILE) -> RedFlagRules:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RulesError(f"could not read {path.name}: {type(error).__name__}") from error
    if not isinstance(raw, dict):
        raise RulesError(f"{path.name} is not a mapping")
    action = (raw.get("medicine_actions") or {}).get("tier2")
    if not isinstance(action, str) or not action.strip():
        raise RulesError("medicine_actions.tier2 needs a pattern")
    return RedFlagRules(
        tier1=_group(raw.get("tier1"), "tier1"),
        tier2=_group(raw.get("tier2"), "tier2"),
        medicine_action=_compile([action], "medicine_actions.tier2")[0],
    )


def normalize(text: str) -> str:
    """Lowercase, straighten curly quotes, and collapse spaces so patterns see plain text."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'").replace("​", "")
    return re.sub(r"\s+", " ", text).strip().lower()


# --- the patient's own warning signs ------------------------------------------------------

# Words that carry no signal on their own in a warning sign like "gain more than 2 pounds in a day".
_FILLER = frozenset(
    "a an and or the of in on at to for from with without than then that this these those is are "
    "was were be been it its you your my me i if when while after before more less much many any "
    "some very new worse worsening getting get got have has had one two three day days week weeks "
    "night nights hour hours pound pounds lb lbs severe sudden suddenly call care team "
    "increasing increase increased either".split()
)
# A clause that is only one of these ("pain" from "swelling, pain, or warmth in either calf")
# would match almost any question, so it counts only next to other words ("chest pain").
_VAGUE_ALONE = frozenset(
    "pain hurt ache sore soreness warm warmth trouble problem discomfort".split()
)
_SUFFIXES = ("ness", "ing", "ed", "es", "s")


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    return word[:-1] + "i" if word.endswith("y") else word


_VAGUE_STEMS = frozenset(_stem(word) for word in _VAGUE_ALONE)


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text)
    return {_stem(word) for word in words if word not in _FILLER and len(word) >= 3}


def _clauses(sign_text: str) -> list[set[str]]:
    parts = re.split(r",|;|\bor\b|\band\b", normalize(sign_text))
    clauses = [_content_words(part) for part in parts]
    return [words for words in clauses if words and not words <= _VAGUE_STEMS]


def matches_warning_sign(question: str, sign: ProfileWarningSign) -> bool:
    """True if the question describes one of the sign's parts (most of its key words appear)."""
    asked = _content_words(normalize(question))
    for clause in _clauses(sign.text):
        needed = max(1, math.ceil(0.6 * len(clause)))
        if len(clause & asked) >= needed:
            return True
    return False


# --- putting it together --------------------------------------------------------------------


def _medicine_pattern(rules: RedFlagRules, names: list[str]) -> re.Pattern[str] | None:
    if not names:
        return None
    alternatives = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
    return re.compile(
        rf"{rules.medicine_action.pattern}.{{0,{NAME_REACH}}}\b(?:{alternatives})\b", re.IGNORECASE
    )


def apply_rules(question: str, context: PatientSafetyContext) -> RuleResult:
    """The tier the fixed rules give this question, and which rules matched."""
    rules = load_rules()
    text = normalize(question)
    hits: list[str] = []
    tier = Tier.GENERAL

    for tier_name, found_tier, groups in (
        ("tier1", Tier.EMERGENCY, rules.tier1),
        ("tier2", Tier.CARE_TEAM, rules.tier2),
    ):
        for category, patterns in groups.items():
            if any(pattern.search(text) for pattern in patterns):
                hits.append(f"{tier_name}:{category}")
                tier = min(tier, found_tier)

    medicine = _medicine_pattern(rules, context.medicine_names)
    if medicine and medicine.search(text):
        hits.append("tier2:medicine_action")
        tier = min(tier, Tier.CARE_TEAM)

    for sign in context.warning_signs:
        if matches_warning_sign(question, sign):
            hits.append(f"profile:{sign.tier.lower()}")
            tier = min(tier, Tier.EMERGENCY if sign.tier == "CALL_911" else Tier.CARE_TEAM)

    return RuleResult(tier=tier, hits=hits)
