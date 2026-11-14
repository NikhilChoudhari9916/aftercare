"""Checks run on every answer, after the model and before the patient sees it.

Plain code, no model: the agents cannot call, skip or change these (CLAUDE.md sections 4 and 6).
A failed answer is regenerated once with the reasons, then replaced by the safe fallback; that
loop belongs to the question graph. This module only says what is wrong.
"""

import re
from collections.abc import Iterable, Mapping
from enum import StrEnum

import textstat
from pydantic import BaseModel

from app.config import Settings
from app.qa.answer_text import cited_ids, parse_answer, plain_text
from app.safety.messages import NO_CARE_TEAM_LINE, TIER1_MESSAGE, safe_fallback
from app.safety.rules import Tier
from app.summary.profile import ConfirmedProfile
from app.summary.schedule import SLOT_TIMES

MIN_WORDS_FOR_READING_LEVEL = 8  # textstat is meaningless on a few words
MIN_NAME_LENGTH = 4  # a shorter name would match inside ordinary words


class Check(StrEnum):
    EMPTY = "EMPTY"
    NOT_EMERGENCY_TEXT = "NOT_EMERGENCY_TEXT"
    UNKNOWN_CITATION = "UNKNOWN_CITATION"
    UNCITED_FACT = "UNCITED_FACT"
    DOSE_MISMATCH = "DOSE_MISMATCH"
    TIME_MISMATCH = "TIME_MISMATCH"
    UNKNOWN_MEDICINE = "UNKNOWN_MEDICINE"
    MEDICINE_ADVICE = "MEDICINE_ADVICE"
    DIAGNOSIS = "DIAGNOSIS"
    TOO_LONG = "TOO_LONG"
    TOO_HARD = "TOO_HARD"
    NO_CARE_TEAM = "NO_CARE_TEAM"


class Failure(BaseModel):
    check: Check
    detail: str  # a plain sentence for the model to fix; it can quote the answer, so never log it


class ValidationResult(BaseModel):
    failures: list[Failure] = []

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def checks(self) -> list[str]:
        """Only the names of the checks that failed. This is what QALog keeps (no patient text)."""
        return [failure.check.value for failure in self.failures]

    def retry_reason(self) -> str:
        """What to tell the model when it must answer again."""
        problems = " ".join(f"({i}) {f.detail}" for i, f in enumerate(self.failures, start=1))
        return f"Your answer failed these checks. Fix them and answer again. {problems}"


def validate_answer(
    raw_answer: str,
    *,
    tier: Tier,
    profile: ConfirmedProfile,
    retrieved: Mapping[str, str],
    settings: Settings,
    evidence: Iterable[str] = (),
) -> ValidationResult:
    """Check a model reply.

    `retrieved` maps each source ID the model was given ("D1", "L2") to its text. `evidence` is
    any other text that may justify a number or time, such as the schedule tool's output.
    """
    visible = parse_answer(raw_answer).visible
    text = plain_text(visible)
    if not text:
        return ValidationResult(
            failures=[Failure(check=Check.EMPTY, detail="The answer was empty.")]
        )
    if tier == Tier.EMERGENCY:
        # The emergency text is fixed words; nothing else may stand in for it.
        same = text == TIER1_MESSAGE
        return ValidationResult(
            failures=[]
            if same
            else [
                Failure(
                    check=Check.NOT_EMERGENCY_TEXT,
                    detail="An emergency must get exactly the fixed emergency message.",
                )
            ]
        )

    names = _medicine_names(profile)
    # Only the sources the answer cites count, so a number or name cannot borrow a source
    # that was retrieved but not cited.
    cited = {cid: retrieved[cid] for cid in set(cited_ids(visible)) if cid in retrieved}
    known = _known_text(profile, cited, evidence)
    lead = _care_team_lead(text, profile)
    body = _without_sentence(text, lead) if lead else text
    sentences = _sentences(visible)

    failures: list[Failure] = []
    failures += _check_citations(visible, retrieved)
    failures += _check_uncited(sentences, names, profile)
    failures += _check_quantities(text, sentences, names, profile, known)
    failures += _check_times(text, known)
    failures += _check_medicine_names(text, known)
    failures += _check_advice(sentences)
    failures += _check_diagnosis(sentences)
    failures += _check_size(body, settings, names)
    if tier == Tier.CARE_TEAM:
        failures += _check_care_team(text, profile)
    return ValidationResult(failures=failures)


def fallback_message(profile: ConfirmedProfile) -> str:
    """The safe answer when two tries failed: send the patient to their pharmacist."""
    for contact in profile.care_team:
        if "pharmac" in contact.name.casefold():
            return safe_fallback(contact.phone)
    return safe_fallback(None)


# --- what is known: the confirmed papers, the sources the model was given, and given evidence ---


def _medicine_names(profile: ConfirmedProfile) -> dict[int, list[str]]:
    """For each confirmed medicine (by position): every name it goes by, lowercase."""
    result: dict[int, list[str]] = {}
    for index, medicine in enumerate(profile.medicines):
        names: list[str] = []
        for name in (medicine.name_as_written, *medicine.other_names):
            words = name.casefold().split()
            for candidate in (" ".join(words), words[0] if words else ""):
                if len(candidate) >= MIN_NAME_LENGTH and candidate not in names:
                    names.append(candidate)
        result[index] = names
    return result


def _medicine_text(profile: ConfirmedProfile, index: int) -> str:
    medicine = profile.medicines[index]
    parts = [medicine.dose, medicine.frequency, medicine.timing, medicine.change_note]
    return " ".join(part for part in (*parts, medicine.source_quote) if part)


def _known_text(
    profile: ConfirmedProfile, retrieved: Mapping[str, str], evidence: Iterable[str]
) -> str:
    """Everything an answer may draw numbers, times and names from, as one lowercase string."""
    parts = [_medicine_text(profile, i) for i in range(len(profile.medicines))]
    for medicine in profile.medicines:
        parts += [medicine.name_as_written, *medicine.other_names]
    parts += [sign.text for sign in profile.warning_signs]
    parts += [f"{item.what} {item.when} {item.with_whom or ''}" for item in profile.follow_ups]
    parts += [limit.text for limit in profile.diet_limits]
    parts += [f"{c.name} {c.phone} {c.hours or ''}" for c in profile.care_team]
    parts += [*retrieved.values(), *evidence]
    return re.sub(r"\b([ap])\.m\.", r"\1m", " ".join(parts).casefold())


# --- sentences ---


def _sentences(visible: str) -> list[str]:
    """Sentences as the patient reads them, each with its [D1] tag kept at the end."""
    flat = re.sub(r"\b([ap])\.m\.", r"\1m", visible.replace("**", ""), flags=re.IGNORECASE)
    flat = re.sub(r"\b(Dr|Mr|Mrs|Ms|St)\.", r"\1", flat)
    flat = re.sub(r"(?m)^\s*\d+\.\s+", "", flat)  # "1. " at the start of a numbered line
    # Split after a sentence end, unless a [D1] tag follows (it belongs to that sentence), and
    # after a tag that is followed by a new sentence ("... pill. [D1] Take it daily.").
    pieces = re.split(r"(?<=[.!?:])\s+(?=[^\[])|(?<=\])\s+(?=[A-Z])|\n+", flat)
    return [" ".join(piece.split()) for piece in pieces if piece.strip()]


def _without_sentence(text: str, sentence: str) -> str:
    return " ".join(text.replace(sentence, "", 1).split())


# --- citations ---


def _check_citations(visible: str, retrieved: Mapping[str, str]) -> list[Failure]:
    unknown = sorted({cid for cid in cited_ids(visible) if cid not in retrieved})
    if not unknown:
        return []
    return [
        Failure(
            check=Check.UNKNOWN_CITATION,
            detail=f"You cited {', '.join(unknown)}, which you were not given. Cite only the "
            "sources provided.",
        )
    ]


_NOT_A_FACT = re.compile(
    r"(don'?t answer|do not answer|not in your papers|not in your paperwork|"
    r"ask your pharmacist|ask your care team|call your care team|call your pharmacist|"
    r"call 911|quick question|which medicine|i can'?t answer)",
    re.IGNORECASE,
)


# Words that make a sentence a claim about when or how to take a medicine, even with no name or
# number. Nouns like "pill" are left out: "don't swap your water pill" makes no claim.
_FACT_WORDS = re.compile(
    r"\b(take|takes|taking|dose|doses|daily|twice|morning|evening|bedtime|night|every)\b",
    re.IGNORECASE,
)
_CLARIFYING = "quick question so i get this right"


def _check_uncited(
    sentences: list[str], names: dict[int, list[str]], profile: ConfirmedProfile
) -> list[Failure]:
    # A clarifying question lists the patient's own medicines and cites nothing (prompt v7,
    # example 3). It must not carry numbers, which still need a source.
    asks_which = bool(sentences) and sentences[0].casefold().startswith(_CLARIFYING)
    if asks_which and not any(re.search(r"\d", sentence) for sentence in sentences):
        return []
    phones = {_digits(c.phone) for c in profile.care_team if c.phone}
    all_names = [name for group in names.values() for name in group]
    uncited = []
    for sentence in sentences:
        if cited_ids(sentence) or sentence.endswith("?") or _NOT_A_FACT.search(sentence):
            continue
        if any(phone and phone in _digits(sentence) for phone in phones):
            continue  # the care team line is the patient's own contact, not a claim
        if (
            re.search(r"\d", sentence)
            or _FACT_WORDS.search(sentence)
            or any(_mentions(sentence, name) for name in all_names)
        ):
            uncited.append(sentence)
    if not uncited:
        return []
    return [
        Failure(
            check=Check.UNCITED_FACT,
            detail="Every sentence with a fact needs a source tag such as [D1] at its end. "
            f"These have none: {' | '.join(uncited)}",
        )
    ]


# --- doses and times ---

_QUANTITY = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(mg|mcg|meq|ml|units?|g|tablets?|capsules?|pills?)\b", re.IGNORECASE
)
_DRUG_UNITS = {"mg", "mcg", "meq", "ml", "g", "unit", "units"}


def _quantities(text: str) -> set[tuple[str, str]]:
    found = set()
    for number, unit in _QUANTITY.findall(text):
        value = number.replace(",", "").rstrip("0").rstrip(".") if "." in number else number
        unit = unit.casefold()
        unit = unit.rstrip("s") if unit not in {"mcg", "meq"} else unit
        found.add((value.replace(",", ""), unit))
    return found


def _check_quantities(
    text: str,
    sentences: list[str],
    names: dict[int, list[str]],
    profile: ConfirmedProfile,
    known: str,
) -> list[Failure]:
    allowed_everywhere = _quantities(known)
    failures = []
    for number, unit in sorted(_quantities(text) - allowed_everywhere):
        failures.append(
            Failure(
                check=Check.DOSE_MISMATCH,
                detail=f"The amount {number} {unit} is not in the patient's confirmed papers or "
                "the sources. Use only amounts from them.",
            )
        )
    # A swap: a sentence about one medicine that states another medicine's dose.
    by_medicine = {
        i: _quantities(_medicine_text(profile, i)) for i in range(len(profile.medicines))
    }
    for sentence in sentences:
        named = {i for i, group in names.items() if any(_mentions(sentence, n) for n in group)}
        if not named:
            continue
        own = set().union(*(by_medicine[i] for i in named))
        others = set().union(*(by_medicine[i] for i in by_medicine if i not in named))
        for quantity in _quantities(sentence):
            if quantity[1] in _DRUG_UNITS and quantity in others and quantity not in own:
                failures.append(
                    Failure(
                        check=Check.DOSE_MISMATCH,
                        detail=f"{quantity[0]} {quantity[1]} belongs to a different medicine "
                        "than the one in that sentence.",
                    )
                )
    return failures


_CLOCK = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\b(\d{1,2}):(\d{2})\b", re.IGNORECASE)


def _times(text: str) -> set[int]:
    """Clock times in the text as minutes after midnight. "8 pm" and "20:00" are the same."""
    found = set()
    for hour, minute, meridiem, hour24, minute24 in _CLOCK.findall(text):
        if meridiem:
            value = int(hour) % 12 + (12 if meridiem.casefold() == "pm" else 0)
            found.add(value * 60 + int(minute or 0))
        else:
            found.add(int(hour24) * 60 + int(minute24))
    return found


def _check_times(text: str, known: str) -> list[Failure]:
    allowed = _times(known) | {t.hour * 60 + t.minute for t in SLOT_TIMES.values()}
    wrong = sorted(_times(text) - allowed)
    return [
        Failure(
            check=Check.TIME_MISMATCH,
            detail=f"The time {m // 60:02d}:{m % 60:02d} is not in the patient's papers or "
            "schedule. Use only times from them.",
        )
        for m in wrong
    ]


# --- medicine names ---

# Endings that make a word look like a medicine. A heuristic, not a drug list: it catches a
# generic name the model brings from nowhere; it cannot catch a brand name.
_DRUG_LOOK = re.compile(
    r"\b[a-z]{3,}(?:pril|sartan|olol|dipine|statin|azole|mycin|cillin|oxacin|caine|codone|"
    r"morphone|parin|xaban|gatran|tidine|prazole|zepam|zolam|formin|semide|thiazide|cycline|"
    r"profen|proxen|farin|oxin|aminophen|spirin|sulin|setron|triptan|dronate|pamide)\b",
    re.IGNORECASE,
)


def _check_medicine_names(text: str, known: str) -> list[Failure]:
    mentioned = {match.group(0).casefold() for match in _DRUG_LOOK.finditer(text)}
    unknown = sorted(word for word in mentioned if not _mentions(known, word))
    return [
        Failure(
            check=Check.UNKNOWN_MEDICINE,
            detail=f"The medicine {word} is not in the patient's papers or the sources. Do not "
            "name medicines that are not in them.",
        )
        for word in unknown
    ]


# --- advice and diagnosis ---

_ATTRIBUTED = re.compile(
    r"(papers?|paperwork|instructions|label|care team|doctor|pharmacist|nurse)\s+"
    r"(say|says|said|state|states|list|lists|tell|tells|told|write|writes)\b|"
    r"\baccording to\b|\b(ask|call|check with|talk to|tell) (your )?"
    r"(pharmacist|care team|doctor|nurse|surgeon)\b",
    re.IGNORECASE,
)
_ADVICE = re.compile(
    r"\b(you |we )?(should|can|could|may|might|need to|must|have to|ought to|are able to)"
    r"\s+(safely\s+|just\s+|go ahead and\s+)?(skip|stop|double|halve|cut|reduce|lower|"
    r"increase|raise|change|switch|restart|start|quit|miss|take (an )?extra|take (more|less)|"
    r"take (two|2|three|3|half)|keep taking|continue taking)\b|"
    r"\bgo ahead and (skip|stop|double|take|start)\b|"
    r"\b(it'?s|it is|that'?s|that is) (ok|okay|fine|safe|alright|normal) to (skip|stop|double|"
    r"take|miss|start|drink)\b|"
    r"(?:^|\.\s*|:\s*)(skip|stop|double|halve|reduce|increase|change|switch|restart)\s+"
    r"(taking|your|the|this|that|it)\b|"
    r"\b(is|are) (ok|okay|fine|safe|alright)\b|"  # "ibuprofen is okay": calling a product safe
    r"\bup to \d|\byou can take \d|\btake (two|2|three|3|an extra|extra)\b|"
    r"\b(you|you'?d) (can|could|may) (buy|get|pick up)\b|\btry (buying|getting|using)\b",
    re.IGNORECASE,
)
_CONDITION = (
    r"(infection|clot|heart attack|stroke|pneumonia|failure|reaction|bleeding|side effect|"
    r"condition|illness|disease|problem)"
)
_DIAGNOSIS = re.compile(
    r"\byou (probably |likely |may |might |could |definitely |maybe )?"
    r"(have|had|are having|are suffering from|suffer from|developed)\s+(a |an |the )?"
    r"(infection|blood clot|clot|heart attack|stroke|pneumonia|dvt|embolism|sepsis|"
    r"kidney (failure|damage|problem)|heart failure|diabetes|bleeding|reaction)\b|"
    r"\b(sounds|looks|seems) like (a |an |you have )|"
    r"\b(this|that|it) (could be|may be|might be|is probably|is likely|is a sign of)\b"
    rf"[^.]{{0,40}}\b{_CONDITION}\b|"
    r"\b(this|that|it) (means you have|is caused by)\b|"
    r"\b(it'?s|that'?s|this is|that is) (normal|nothing to worry about)\b|"  # reassurance
    r"\b(may|might|could) be (caused by|due to)\b",
    re.IGNORECASE,
)


def _check_advice(sentences: list[str]) -> list[Failure]:
    bad = []
    for sentence in sentences:
        match = _ADVICE.search(sentence)
        if match is None:
            continue
        attributed = _ATTRIBUTED.search(sentence)
        if attributed and attributed.start() < match.start():
            continue  # "Your papers say to stop..." reports the papers; it is not our advice
        bad.append(sentence)
    if not bad:
        return []
    return [
        Failure(
            check=Check.MEDICINE_ADVICE,
            detail="Never tell the patient to start, stop, skip, double or change a medicine, "
            "or what to buy. Say what the papers say and suggest the pharmacist. Rewrite: "
            + " | ".join(bad),
        )
    ]


def _check_diagnosis(sentences: list[str]) -> list[Failure]:
    bad = [sentence for sentence in sentences if _DIAGNOSIS.search(sentence)]
    if not bad:
        return []
    return [
        Failure(
            check=Check.DIAGNOSIS,
            detail="Never say what condition the patient has or what is causing a symptom. "
            "Rewrite: " + " | ".join(bad),
        )
    ]


# --- size, reading level, care team ---


def _mask_medicines(body: str, names: dict[int, list[str]]) -> str:
    """Swap medicine names for a short word before scoring the reading level.

    A name like "acetaminophen" cannot be made easier, and its syllables would push a short,
    plain sentence far above its real grade.
    """
    masked = _DRUG_LOOK.sub("medicine", body)
    for group in names.values():
        for name in sorted(group, key=len, reverse=True):
            masked = re.sub(
                rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])",
                "medicine",
                masked,
                flags=re.IGNORECASE,
            )
    return masked


def _check_size(body: str, settings: Settings, names: dict[int, list[str]]) -> list[Failure]:
    failures = []
    words = len(body.split())
    if words > settings.max_answer_words:
        failures.append(
            Failure(
                check=Check.TOO_LONG,
                detail=f"The answer has {words} words. Keep it under {settings.max_answer_words}.",
            )
        )
    if words >= MIN_WORDS_FOR_READING_LEVEL:
        grade = textstat.flesch_kincaid_grade(_mask_medicines(body, names))
        if grade > settings.max_reading_grade:
            failures.append(
                Failure(
                    check=Check.TOO_HARD,
                    detail=f"The reading level is grade {grade:.0f}. Use shorter sentences and "
                    "everyday words, about 6th grade.",
                )
            )
    return failures


def _care_team_lead(text: str, profile: ConfirmedProfile) -> str | None:
    """The first sentence, if it is the care team line."""
    first = _first_sentence(text)
    return first if _names_care_team(first, profile) else None


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]


def _names_care_team(text: str, profile: ConfirmedProfile) -> bool:
    if not profile.care_team:
        return NO_CARE_TEAM_LINE.casefold().rstrip(".") in text.casefold()
    lowered = text.casefold()
    return any(
        _digits(contact.phone) in _digits(text) and contact.name.casefold() in lowered
        for contact in profile.care_team
        if contact.phone
    )


def _check_care_team(text: str, profile: ConfirmedProfile) -> list[Failure]:
    lead = re.split(r"(?<=[.!?])\s+", text, maxsplit=2)[:2]
    if any(_names_care_team(part, profile) for part in lead):
        return []
    return [
        Failure(
            check=Check.NO_CARE_TEAM,
            detail="A needs-the-care-team answer must start with the care team's name and phone "
            "number from the patient's papers.",
        )
    ]


# --- small helpers ---


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _mentions(text: str, word: str) -> bool:
    return (
        re.search(rf"(?<![a-z0-9]){re.escape(word.casefold())}(?![a-z0-9])", text.casefold())
        is not None
    )
