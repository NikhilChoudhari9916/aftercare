from app.ingestion.pdf_reader import FRIENDLY_MESSAGES

JOB_ERROR_MESSAGES = {
    **FRIENDLY_MESSAGES,
    "ai_unavailable": (
        "AfterCare's reading service isn't available right now. Please try again in a few minutes."
    ),
    "ai_refused": (
        "AfterCare couldn't process this document. Please check that it is your discharge papers."
    ),
    "extraction_failed": (
        "AfterCare couldn't read this document reliably. "
        "Please try again, or upload a clearer digital copy."
    ),
    "interrupted": "The upload was interrupted. Please try again.",
    "internal_error": "Something went wrong on our side. Please try again.",
}


def friendly_error(code: str | None) -> str | None:
    if code is None:
        return None
    return JOB_ERROR_MESSAGES.get(code, JOB_ERROR_MESSAGES["internal_error"])
