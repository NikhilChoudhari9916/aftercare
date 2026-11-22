"""Fail-closed checks that each answer claim is supported by its cited paper passages."""

import json
import re
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.config import Settings
from app.llm import LLM
from app.prompts import load_prompt
from app.qa.answer_text import cited_ids, parse_answer, plain_text
from app.qa.validators import Check, Failure, ValidationResult, _care_team_lead, _sentences
from app.summary.profile import ConfirmedProfile

NOT_STATED = "Your uploaded papers don't provide that information."
NO_PURPOSE = "Your uploaded papers don't explain what this medicine is for."
CLARIFY_MEDICINE = "Quick question so I get this right: Which medicine do you mean?"
SAFE_REPLIES = frozenset(
    {
        NOT_STATED,
        NO_PURPOSE,
        CLARIFY_MEDICINE,
        # Historical v7 fixtures; these abstain without asserting medical facts.
        "Your papers and drug labels here don't answer this. Please ask your pharmacist.",
        "Your papers and drug labels here don't answer this. "
        "Please ask your pharmacist before drinking alcohol.",
    }
)
PAPER_ID = re.compile(r"D[1-9]\d*")
SAFE_FOLLOWUPS = frozenset(
    {
        "What changed?",
        "When do I take it?",
        "When do my papers say to take it?",
        "What dose is listed?",
        "What other names are listed?",
        "What follow-up visits are listed?",
        "Which medicine was stopped?",
        "When should I call 911 instead?",
        "What do the papers say about food?",
    }
)


class QuoteEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    quote: str = Field(min_length=1)


class ClaimVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: int
    supported: StrictBool
    evidence: list[QuoteEvidence]


class GroundingVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[ClaimVerdict]


def _failure(detail: str) -> ValidationResult:
    return ValidationResult(failures=[Failure(check=Check.UNSUPPORTED_CLAIM, detail=detail)])


def _flat(text: str) -> str:
    return " ".join(text.split()).casefold()


def check_paper_support(
    raw: str,
    *,
    profile: ConfirmedProfile,
    retrieved: Mapping[str, str],
    llm: LLM,
    settings: Settings,
    searched_papers: bool | None = None,
) -> ValidationResult:
    """Judge only the supplied paper evidence; never use memory or outside references.

    The model reviews explicitly enumerated claims. Code requires one verdict per claim and
    verifies that every supporting quote exists in a source that the same claim actually cites.
    An unavailable reviewer, malformed verdict, missing quote or unsupported claim fails closed.
    """
    visible = parse_answer(raw).visible
    if any(not PAPER_ID.fullmatch(cid) or cid not in retrieved for cid in cited_ids(visible)):
        return _failure("Only retrieved paper citations may be used, even in an abstention.")
    searched = bool(retrieved) if searched_papers is None else searched_papers
    policy_text = plain_text(visible).replace("’", "'")
    if policy_text in SAFE_REPLIES:
        if policy_text != CLARIFY_MEDICINE and not searched:
            return _failure(
                "Search the uploaded papers before concluding that information is absent."
            )
        return ValidationResult()
    lead = _care_team_lead(plain_text(visible), profile)
    claims = []
    abstained = False
    for sentence in _sentences(visible):
        text = plain_text(sentence)
        if lead and text == lead:
            continue  # already checked against confirmed paper contact details
        if text.replace("’", "'") in {NOT_STATED, NO_PURPOSE}:
            if not searched:
                return _failure(
                    "Search the uploaded papers before stating that information is absent."
                )
            abstained = True
            continue
        ids = set(cited_ids(sentence))
        if not ids or any(not PAPER_ID.fullmatch(cid) or cid not in retrieved for cid in ids):
            return _failure(
                "Every factual sentence needs a retrieved paper citation, such as [D1]."
            )
        claims.append({"id": len(claims), "text": text, "source_ids": sorted(ids)})
    if not claims and abstained:
        return ValidationResult()
    if not claims:
        return _failure("Use a supported paper fact or the exact not-stated response.")
    ids = {cid for claim in claims for cid in claim["source_ids"]}
    request = {
        "claims": claims,
        "paper_passages": {cid: retrieved[cid] for cid in sorted(ids)},
    }
    try:
        report = llm.extract(
            model=settings.model_fast,
            system=load_prompt("paper_support_system_prompt_v1.txt"),
            user=json.dumps(request),
            schema=GroundingVerdict,
            max_tokens=1000,
        )
    except Exception:  # reviewer problems must never let an unverified answer through
        return _failure("Paper support could not be verified. Use only supported facts or abstain.")
    if not isinstance(report, GroundingVerdict):
        return _failure("The paper-support verdict was unreadable.")
    if sorted(v.claim_id for v in report.claims) != list(range(len(claims))):
        return _failure("Every answer claim must be checked exactly once.")
    for verdict in report.claims:
        if not verdict.supported or not verdict.evidence:
            return _failure(
                "A claim is not directly supported by its cited paper. Remove it or abstain."
            )
        allowed = claims[verdict.claim_id]["source_ids"]
        for proof in verdict.evidence:
            if (
                proof.source_id not in allowed
                or not _flat(proof.quote)
                or _flat(proof.quote) not in _flat(retrieved[proof.source_id])
            ):
                return _failure(
                    "Supporting quotes must occur in the paper passages that claim cites."
                )
    return ValidationResult()
