from dataclasses import dataclass
from pathlib import Path

from app.ingestion.pdf_reader import read_pdf
from app.qa.chunker import MAX_CHUNK_CHARS, build_chunks, chunk_pages, medicine_chunks
from tests.summary.helpers import confirmed

PATIENT1_PDF = Path(__file__).resolve().parents[2] / "data/synthetic/patient1_discharge_summary.pdf"
HEADER = "Riverbend General Hospital\nMILLER, JORDAN MRN SYN-004217 Page 1 of 2"
SENTENCE = "Weigh yourself every morning after using the bathroom and before breakfast."


@dataclass
class Page:
    number: int
    text: str


def test_a_page_is_split_at_its_own_headings():
    page = Page(
        1,
        f"Salt (sodium)\nLimit sodium to less than 2,000 mg per day each day.\n"
        f"Daily weight\n{SENTENCE}",
    )

    chunks = chunk_pages([page])

    assert [(c.page, c.section) for c in chunks] == [(1, "Salt (sodium)"), (1, "Daily weight")]
    assert chunks[0].text.startswith("Limit sodium")
    assert chunks[1].text == SENTENCE


def test_lines_that_repeat_on_every_page_are_dropped_because_they_name_the_patient():
    pages = [
        Page(1, f"{HEADER}\nDaily weight\n{SENTENCE}"),
        Page(2, f"{HEADER.replace('1 of', '2 of')}\nSalt (sodium)\n{SENTENCE} Limit it."),
    ]

    text = " ".join(chunk.text for chunk in chunk_pages(pages))

    assert "MILLER" not in text
    assert "SYN-004217" not in text
    assert "Riverbend" not in text


def test_a_single_page_keeps_all_its_lines():
    chunks = chunk_pages([Page(1, f"{HEADER}\nDaily weight\n{SENTENCE}")])

    assert "Riverbend" in " ".join(chunk.text for chunk in chunks) + " ".join(
        chunk.section for chunk in chunks
    )


def test_a_label_in_capitals_is_not_a_heading():
    page = Page(1, f"Your medicine list\n{SENTENCE}\nSTOPPED\n{SENTENCE} Again, please.")

    sections = {chunk.section for chunk in chunk_pages([page])}

    assert sections == {"Your medicine list"}


def test_a_long_section_is_cut_between_lines_into_pieces_of_about_a_paragraph():
    lines = [
        f"Walk every day for a while, number {i}, and rest when you feel tired." for i in range(30)
    ]
    page = Page(1, "Activity\n" + "\n".join(lines))

    chunks = chunk_pages([page])

    assert len(chunks) > 1
    assert all(chunk.section == "Activity" for chunk in chunks)
    assert all(len(chunk.text) <= MAX_CHUNK_CHARS for chunk in chunks)


def test_a_heading_with_nothing_under_it_makes_no_chunk():
    page = Page(1, f"Intro heading\nShort\nDaily weight\n{SENTENCE}")

    assert [chunk.section for chunk in chunk_pages([page])] == ["Daily weight"]


def test_a_page_that_opens_with_a_title_names_its_chunk_after_it():
    page = Page(1, f"Your follow-up appointments\nWhat When Where\nlab visit\n{SENTENCE}")

    (chunk,) = chunk_pages([page])

    assert chunk.section == "Your follow-up appointments"
    assert "Your follow-up appointments" not in chunk.text


def test_each_confirmed_medicine_is_its_own_chunk_with_the_papers_words():
    chunks = medicine_chunks(confirmed())

    assert len(chunks) == 6
    furosemide = chunks[0]
    assert furosemide.section == "Your medicine list"
    assert "furosemide (also known as LASIX)" in furosemide.text
    assert "Dose: 40 mg." in furosemide.text
    assert "How often: once daily in the morning." in furosemide.text
    assert "Status: CHANGED." in furosemide.text
    assert 'Your papers say: "Take 1 tablet (40 mg)' in furosemide.text
    assert "Status: AS NEEDED." in chunks[4].text
    assert "Status: STOPPED." in chunks[5].text


def test_a_medicine_missing_from_the_confirmed_profile_has_no_chunk():
    profile = confirmed()
    profile = profile.model_copy(update={"medicines": profile.medicines[1:]})

    text = " ".join(chunk.text for chunk in medicine_chunks(profile))

    assert "furosemide" not in text


def test_the_real_patient_1_pdf_is_cut_by_its_sections_without_the_hospital_header():
    pages = read_pdf(PATIENT1_PDF.read_bytes(), max_pages=30)

    chunks = build_chunks(pages, confirmed())
    papers = " ".join(f"{c.section} {c.text}" for c in chunks)

    assert {"Why you were in the hospital", "When to call your care team"} <= {
        c.section for c in chunks
    }
    assert "MILLER" not in papers and "SYN-004217" not in papers and "03/14/1959" not in papers
    assert "Limit sodium to less than 2,000 mg per day" in papers
    assert all(len(c.text) <= MAX_CHUNK_CHARS + 120 for c in chunks)
    assert {c.page for c in chunks} == {1, 2, 3}
