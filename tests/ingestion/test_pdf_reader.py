import pymupdf
import pytest

from app.ingestion.pdf_reader import FRIENDLY_MESSAGES, PdfError, read_pdf
from tests.samples import PATIENT1_PDF


def make_pdf(*page_texts: str) -> bytes:
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    return document.tobytes()


LONG_TEXT = "Take one tablet by mouth every day. " * 3


def test_the_synthetic_discharge_pdf_is_read_page_by_page():
    pages = read_pdf(PATIENT1_PDF.read_bytes(), max_pages=30)

    assert [page.number for page in pages] == [1, 2, 3]
    assert "furosemide" in pages[0].text
    assert "Cardiology Nurse Line" in pages[1].text
    assert "Primary care follow-up" in pages[2].text


def test_a_file_that_is_not_a_pdf_is_rejected():
    for data in (b"", b"hello world", b"\x89PNG\r\n\x1a\n" + b"x" * 100):
        with pytest.raises(PdfError) as raised:
            read_pdf(data, max_pages=30)
        assert raised.value.code == "not_a_pdf"


def test_a_corrupt_pdf_is_rejected():
    with pytest.raises(PdfError) as raised:
        read_pdf(b"%PDF-1.7\nthis is not a real pdf body", max_pages=30)
    assert raised.value.code == "not_a_pdf"


def test_a_pdf_with_no_text_layer_is_rejected_as_a_scan():
    with pytest.raises(PdfError) as raised:
        read_pdf(make_pdf("", ""), max_pages=30)
    assert raised.value.code == "no_text_layer"


def test_a_pdf_with_too_many_pages_is_rejected():
    with pytest.raises(PdfError) as raised:
        read_pdf(make_pdf(LONG_TEXT, LONG_TEXT, LONG_TEXT), max_pages=2)
    assert raised.value.code == "too_many_pages"


def test_a_file_over_the_size_limit_is_rejected_before_it_is_opened():
    with pytest.raises(PdfError) as raised:
        read_pdf(make_pdf(LONG_TEXT), max_pages=30, max_bytes=100)
    assert raised.value.code == "too_large"


def test_every_error_has_a_friendly_message_with_no_jargon():
    for code, message in FRIENDLY_MESSAGES.items():
        assert PdfError(code).friendly_message == message
        assert message.endswith(".")
    assert "scan" in FRIENDLY_MESSAGES["no_text_layer"]
