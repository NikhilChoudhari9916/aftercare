from dataclasses import dataclass

import pymupdf

MIN_TEXT_CHARS_PER_PAGE = 40

FRIENDLY_MESSAGES = {
    "not_a_pdf": "That file isn't a PDF. Please upload your discharge papers as a PDF.",
    "too_large": "That PDF is too large. Please upload a smaller file.",
    "too_many_pages": "That PDF has too many pages. Please upload only the discharge papers.",
    "no_text_layer": (
        "This PDF looks like a scan or photo, and AfterCare can only read PDFs with real text "
        "for now. Please upload the digital copy from your hospital's patient portal."
    ),
}


class PdfError(Exception):
    """A PDF we can't use. `code` is a key of FRIENDLY_MESSAGES; the text never has patient data."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    @property
    def friendly_message(self) -> str:
        return FRIENDLY_MESSAGES[self.code]


@dataclass(frozen=True)
class PdfPage:
    number: int  # 1-based, as the patient sees it
    text: str


def read_pdf(data: bytes, *, max_pages: int, max_bytes: int | None = None) -> list[PdfPage]:
    """Return the text of each page, or raise PdfError."""
    if max_bytes is not None and len(data) > max_bytes:
        raise PdfError("too_large")
    if not data.lstrip().startswith(b"%PDF-"):
        raise PdfError("not_a_pdf")

    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as error:  # PyMuPDF raises several unrelated types on corrupt files
        raise PdfError("not_a_pdf") from error

    with document:
        if document.needs_pass or document.page_count == 0:
            raise PdfError("not_a_pdf")
        if document.page_count > max_pages:
            raise PdfError("too_many_pages")
        pages = [
            PdfPage(number=index + 1, text=page.get_text("text", sort=True))
            for index, page in enumerate(document)
        ]

    total_chars = sum(len(page.text.strip()) for page in pages)
    if total_chars < MIN_TEXT_CHARS_PER_PAGE * len(pages):
        raise PdfError("no_text_layer")
    return pages
