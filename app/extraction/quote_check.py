import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.extraction.schema import SOURCED_SECTIONS, ExtractedProfile
from app.ingestion.pdf_reader import PdfPage

# The longest run of matching text must cover at least this share of the quote.
FUZZY_MIN_SHARE = 0.85


@dataclass(frozen=True)
class QuoteFinding:
    section: str
    index: int
    status: str  # "verified", "page_corrected", or "not_found"
    claimed_page: int
    matched_page: int | None


def normalize_for_matching(text: str) -> str:
    """Lowercase, and let punctuation, dashes, and line breaks all count as one space."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _share_of_quote_found(page_text: str, quote: str) -> float:
    if not quote:
        return 0.0
    if quote in page_text:
        return 1.0
    longest = SequenceMatcher(None, page_text, quote, autojunk=False).find_longest_match(
        0, len(page_text), 0, len(quote)
    )
    return longest.size / len(quote)


def _check_one(quote: str, claimed_page: int, pages: list[PdfPage]) -> tuple[str, int | None]:
    normalized_quote = normalize_for_matching(quote)
    shares = {
        page.number: _share_of_quote_found(normalize_for_matching(page.text), normalized_quote)
        for page in pages
    }
    if shares.get(claimed_page, 0.0) >= FUZZY_MIN_SHARE:
        return "verified", claimed_page
    best_page, best_share = max(shares.items(), key=lambda item: item[1], default=(None, 0.0))
    if best_page is not None and best_share >= FUZZY_MIN_SHARE:
        return "page_corrected", best_page
    return "not_found", None


def check_quotes(profile: ExtractedProfile, pages: list[PdfPage]) -> list[QuoteFinding]:
    """Check that every quote the model gave really is in the document."""
    findings = []
    for section in SOURCED_SECTIONS:
        for index, item in enumerate(getattr(profile, section)):
            status, matched = _check_one(item.source_quote, item.source_page, pages)
            findings.append(QuoteFinding(section, index, status, item.source_page, matched))
    return findings


def unmatched(findings: list[QuoteFinding]) -> list[QuoteFinding]:
    return [finding for finding in findings if finding.status == "not_found"]


def correct_pages(profile: ExtractedProfile, findings: list[QuoteFinding]) -> ExtractedProfile:
    """Where the quote is real but on another page, fix the page number."""
    updates: dict[str, list] = {}
    for finding in findings:
        if finding.status != "page_corrected":
            continue
        items = updates.setdefault(finding.section, list(getattr(profile, finding.section)))
        items[finding.index] = items[finding.index].model_copy(
            update={"source_page": finding.matched_page}
        )
    return profile.model_copy(update=updates)
