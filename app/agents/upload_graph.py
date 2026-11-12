from collections.abc import Iterator
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.config import Settings
from app.extraction.abbreviations import normalize_profile
from app.extraction.extractor import extract_profile
from app.extraction.injection_scan import InjectionFlag, scan_for_instructions
from app.extraction.quote_check import QuoteFinding, check_quotes, correct_pages, unmatched
from app.extraction.schema import ExtractedProfile
from app.ingestion.pdf_reader import PdfError, PdfPage, read_pdf
from app.llm import LLM, LLMError, LLMRefused, LLMUnavailable


class UploadState(TypedDict, total=False):
    pdf_bytes: bytes
    pages: list[PdfPage]
    profile: ExtractedProfile
    findings: list[QuoteFinding]
    injection_flags: list[InjectionFlag]
    feedback: str | None
    attempts: int
    error: str | None  # a PdfError code, or ai_unavailable, ai_refused, extraction_failed


def _feedback_for(findings: list[QuoteFinding]) -> str:
    where = ", ".join(f"{finding.section} #{finding.index + 1}" for finding in findings)
    return (
        f"These items had a source_quote that is not in the document: {where}. "
        "For each one, copy the exact words from the document, or leave the item out "
        "if the document does not say it."
    )


def build_upload_graph(llm: LLM, settings: Settings):
    """Workflow 1: PDF in, a structured profile out, ready for the patient to confirm.

    ingest -> extract -> check_quotes -> normalize, with two conditional edges:
    an unusable PDF or a failed model call ends early, and quotes the model did not copy
    exactly send it back to extract once (then they are flagged for the patient instead).
    """

    def ingest(state: UploadState) -> dict[str, Any]:
        try:
            pages = read_pdf(
                state["pdf_bytes"],
                max_pages=settings.max_pdf_pages,
                max_bytes=settings.max_pdf_mb * 1024 * 1024,
            )
        except PdfError as error:
            return {"error": error.code}
        return {"pages": pages, "injection_flags": scan_for_instructions(pages), "attempts": 0}

    def extract(state: UploadState) -> dict[str, Any]:
        try:
            profile = extract_profile(llm, settings, state["pages"], state.get("feedback"))
        except LLMUnavailable:
            return {"error": "ai_unavailable"}
        except LLMRefused:
            return {"error": "ai_refused"}
        except LLMError:
            return {"error": "extraction_failed"}
        return {"profile": profile, "attempts": state.get("attempts", 0) + 1}

    def check(state: UploadState) -> dict[str, Any]:
        findings = check_quotes(state["profile"], state["pages"])
        profile = correct_pages(state["profile"], findings)
        bad = unmatched(findings)
        return {
            "profile": profile,
            "findings": findings,
            "feedback": _feedback_for(bad) if bad else None,
        }

    def normalize(state: UploadState) -> dict[str, Any]:
        return {"profile": normalize_profile(state["profile"])}

    def after_ingest(state: UploadState) -> str:
        return END if state.get("error") else "extract"

    def after_extract(state: UploadState) -> str:
        return END if state.get("error") else "check_quotes"

    def after_check(state: UploadState) -> str:
        retry = (
            unmatched(state["findings"]) and state["attempts"] < settings.max_extraction_attempts
        )
        return "extract" if retry else "normalize"

    graph = StateGraph(UploadState)
    graph.add_node("ingest", ingest)
    graph.add_node("extract", extract)
    graph.add_node("check_quotes", check)
    graph.add_node("normalize", normalize)
    graph.add_edge(START, "ingest")
    graph.add_conditional_edges("ingest", after_ingest, {"extract": "extract", END: END})
    graph.add_conditional_edges(
        "extract", after_extract, {"check_quotes": "check_quotes", END: END}
    )
    graph.add_conditional_edges(
        "check_quotes", after_check, {"extract": "extract", "normalize": "normalize"}
    )
    graph.add_edge("normalize", END)
    return graph.compile()


def iter_upload(llm: LLM, settings: Settings, pdf_bytes: bytes) -> Iterator[tuple[str, dict]]:
    """Run the graph and yield (node name, what that node added) as each node finishes."""
    graph = build_upload_graph(llm, settings)
    for chunk in graph.stream({"pdf_bytes": pdf_bytes}, stream_mode="updates"):
        yield from chunk.items()


def run_upload(llm: LLM, settings: Settings, pdf_bytes: bytes) -> UploadState:
    return build_upload_graph(llm, settings).invoke({"pdf_bytes": pdf_bytes})
