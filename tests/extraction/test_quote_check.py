from app.extraction.quote_check import (
    check_quotes,
    correct_pages,
    normalize_for_matching,
    unmatched,
)
from app.ingestion.pdf_reader import PdfPage, read_pdf
from tests.samples import PATIENT1_PDF, patient1_profile


def real_pages() -> list[PdfPage]:
    return read_pdf(PATIENT1_PDF.read_bytes(), max_pages=30)


def with_medicine_quote(quote: str, page: int = 1):
    profile = patient1_profile()
    medicines = list(profile.medicines)
    medicines[0] = medicines[0].model_copy(update={"source_quote": quote, "source_page": page})
    return profile.model_copy(update={"medicines": medicines})


def test_a_good_extraction_of_the_synthetic_pdf_has_every_quote_verified():
    findings = check_quotes(patient1_profile(), real_pages())

    assert len(findings) == 6 + 2 + 1 + 1 + 1
    assert [f for f in findings if f.status != "verified"] == []


def test_line_breaks_punctuation_and_case_do_not_matter():
    quote = "TAKE 1 tablet (40 mg)\n by mouth once daily — in the morning"
    findings = check_quotes(with_medicine_quote(quote), real_pages())
    assert findings[0].status == "verified"


def test_one_small_error_in_a_long_quote_is_still_accepted():
    quote = "Take 1 tablet (40 mg) by mouth once daily in the mornin"
    assert check_quotes(with_medicine_quote(quote), real_pages())[0].status == "verified"


def test_a_made_up_quote_is_not_found():
    quote = "Take two tablets of furosemide at bedtime with grapefruit juice."
    findings = check_quotes(with_medicine_quote(quote), real_pages())
    assert findings[0].status == "not_found"
    assert findings[0].matched_page is None
    assert unmatched(findings) == [findings[0]]


def test_a_real_quote_on_the_wrong_page_is_found_and_the_page_is_corrected():
    profile = with_medicine_quote("Take 1 tablet (40 mg) by mouth once daily in the morning.", 3)
    findings = check_quotes(profile, real_pages())

    assert findings[0].status == "page_corrected"
    assert (findings[0].claimed_page, findings[0].matched_page) == (3, 1)

    fixed = correct_pages(profile, findings)
    assert fixed.medicines[0].source_page == 1
    assert fixed.medicines[1].source_page == 1  # untouched items stay as they were


def test_an_empty_quote_is_never_verified():
    assert check_quotes(with_medicine_quote(""), real_pages())[0].status == "not_found"


def test_normalizing_keeps_only_lowercase_letters_and_digits_as_words():
    assert normalize_for_matching("Sig: 500–1,000 mg PO") == "sig 500 1 000 mg po"
