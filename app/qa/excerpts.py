"""Release original excerpts, never model-authored clinical interpretations (ADR-0046)."""

import re
from dataclasses import dataclass

from app.extraction.injection_scan import PATTERNS
from app.qa.answer_text import cited_ids, parse_answer, plain_text
from app.qa.grounding import CLARIFY_MEDICINE, SAFE_REPLIES
from app.qa.references import named_medicines
from app.qa.sources import PAPERS, SourceBook
from app.safety.messages import NO_CARE_TEAM_LINE
from app.safety.rules import Tier
from app.summary.profile import ConfirmedProfile

PURPOSE = re.compile(
    r"\b(?:what .{0,80}(?:for|purpose)|why .{0,80}(?:take|prescribed)|purpose)\b", re.I
)
NO_VERIFIED_TEXT = "I couldn't verify an answer in the original document text."
NO_VERIFIED_PURPOSE = "I couldn't verify a medicine purpose in the retrieved original text."


@dataclass(frozen=True)
class ExcerptAnswer:
    text: str
    cited: list[str]
    blocked: bool = False


def _explicit_purpose(text: str, question: str, profile: ConfirmedProfile) -> bool:
    requested = named_medicines(profile, question)
    if not requested and not re.search(
        r"\b(?:each|all|my)\b.*\b(?:medicines|medications)\b", question, re.I
    ):
        return False
    medicines = [m for m in profile.medicines if not requested or m.name_as_written in requested]
    for medicine in medicines:
        names = [medicine.name_as_written, *medicine.other_names]
        for name in names:
            escaped = re.escape(name)
            # These select literal statements, not an inferred relationship between a time,
            # medicine and condition. The whole source passage remains visible, with negation.
            if re.search(
                rf"\b{escaped}\b (?:is (?:used|prescribed) for|treats) ", text, re.I
            ) or re.search(rf"\bFor [^.;!?]{{1,60}}, (?:use|take) {escaped}\b", text, re.I):
                return True
    return False


def release_excerpts(
    raw: str, *, question: str, sources: SourceBook, profile: ConfirmedProfile, tier: Tier
) -> ExcerptAnswer:
    """The draft selects D IDs only. Its claims, quotes and interpretation are discarded.

    Provenance comes from server-side retrieval, which compares chunks with this patient's
    current original DocumentPage. A support judge's approval cannot bypass this gate.
    """
    visible = parse_answer(raw).visible
    ids = list(dict.fromkeys(cited_ids(visible)))
    verified = [
        cid
        for cid in ids
        if (
            sources.meta.get(cid, {}).get("kind") == PAPERS
            and sources.meta.get(cid, {}).get("original_document") is True
            and sources.texts.get(cid, "").strip()
            and not any(pattern.search(sources.texts[cid]) for pattern in PATTERNS.values())
        )
    ]
    if PURPOSE.search(question):
        verified = [
            cid for cid in verified if _explicit_purpose(sources.texts[cid], question, profile)
        ]
        if not verified:
            text = NO_VERIFIED_PURPOSE if sources.paper_search_completed else NO_VERIFIED_TEXT
            return ExcerptAnswer(_lead(text, tier), [], blocked=bool(ids))
    if ids and len(verified) != len(ids):
        return ExcerptAnswer(_lead(NO_VERIFIED_TEXT, tier), [], blocked=bool(ids))
    if not verified:
        policy = plain_text(visible).replace("’", "'")
        # Only fixed nonclinical responses can be released without an original excerpt.
        if policy == CLARIFY_MEDICINE:
            return ExcerptAnswer(_lead(CLARIFY_MEDICINE, tier), [])
        if policy in SAFE_REPLIES and sources.paper_search_completed:
            return ExcerptAnswer(_lead(NO_VERIFIED_TEXT, tier), [], blocked=bool(ids))
        return ExcerptAnswer(_lead(NO_VERIFIED_TEXT, tier), [], blocked=bool(ids))
    # No slicing into an excerpt: this preserves negations and qualifications that a model
    # might drop from its chosen substring. The UI escapes the entire returned source text.
    quotes = [f"Original document excerpt:\n{sources.texts[cid]} [{cid}]" for cid in verified]
    return ExcerptAnswer(_lead("\n\n".join(quotes), tier), verified)


def _lead(text: str, tier: Tier) -> str:
    # A fixed instruction rather than a possibly mis-extracted phone number/name.
    return f"{NO_CARE_TEAM_LINE}\n\n{text}" if tier == Tier.CARE_TEAM else text
