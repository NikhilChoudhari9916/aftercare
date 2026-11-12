from app.config import Settings
from app.extraction.schema import ExtractedProfile
from app.ingestion.pdf_reader import PdfPage
from app.llm import LLM
from app.prompts import load_prompt

EXTRACTION_PROMPT = "extraction_system_prompt_v1.txt"


def build_document_text(pages: list[PdfPage]) -> str:
    return "\n\n".join(f"[Page {page.number}]\n{page.text.strip()}" for page in pages)


def extract_profile(
    llm: LLM, settings: Settings, pages: list[PdfPage], feedback: str | None = None
) -> ExtractedProfile:
    """One model call that turns the document text into the structured profile."""
    user = build_document_text(pages)
    if feedback:
        user += f"\n\n---\nCorrection needed: {feedback}"
    return llm.extract(
        model=settings.model_main,
        system=load_prompt(EXTRACTION_PROMPT),
        user=user,
        schema=ExtractedProfile,
        max_tokens=8192,
        effort="medium",
    )
