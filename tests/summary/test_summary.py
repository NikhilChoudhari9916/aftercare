import re

import textstat

from app.extraction.schema import MedStatus
from app.summary.summary import build_summary
from tests.samples import medicine
from tests.summary.helpers import confirmed


def lines(summary, key):
    section = next((s for s in summary.sections if s.key == key), None)
    return [] if section is None else [line.text for line in section.lines]


def test_patient_one_summary_follows_the_papers_section_by_section():
    summary = build_summary(confirmed())

    assert [s.key for s in summary.sections] == [
        "medicines",
        "follow_ups",
        "call_911",
        "call_care_team",
        "diet",
        "care_team",
    ]
    medicines = lines(summary, "medicines")
    assert any("furosemide" in t and "has changed" in t and "40 mg" in t for t in medicines)
    assert any("amlodipine" in t and "stop" in t for t in medicines)
    assert any("acetaminophen" in t and "only when needed" in t for t in medicines)
    assert lines(summary, "call_911")[0].startswith("Your papers say to call 911 for")
    assert "(555) 010-0142" in lines(summary, "care_team")[0]


def test_every_line_points_back_to_a_page_of_the_papers():
    summary = build_summary(confirmed())
    assert all(line.source_page for s in summary.sections for line in s.lines)


def test_it_reads_at_about_a_sixth_grade_level():
    summary = build_summary(confirmed())
    text = " ".join(line.text for s in summary.sections for line in s.lines)
    assert textstat.flesch_kincaid_grade(text) <= 7
    assert textstat.flesch_kincaid_grade(summary.intro) <= 6


def test_no_sentence_ends_with_two_full_stops():
    summary = build_summary(confirmed())
    assert not any(".." in line.text for s in summary.sections for line in s.lines)


def test_it_never_diagnoses_or_gives_dose_advice():
    summary = build_summary(confirmed())
    text = " ".join([summary.intro] + [line.text for s in summary.sections for line in s.lines])

    assert not re.search(r"\byou have\b|diagnos|you should (start|stop|take|skip)", text, re.I)
    assert not re.search(r"double|skip a dose|increase|decrease", text, re.I)


def test_empty_sections_are_left_out():
    summary = build_summary(confirmed(follow_ups=[], diet_limits=[], care_team=[]))
    assert [s.key for s in summary.sections] == ["medicines", "call_911", "call_care_team"]


def test_a_medicine_with_missing_details_still_reads_cleanly():
    bare = medicine("testol", [], None, None, MedStatus.NEW, "q")
    summary = build_summary(confirmed(medicines=[bare]))
    assert lines(summary, "medicines") == ["Your papers list a new medicine: testol."]


# --- one card for each medicine ---


def test_every_medicine_has_a_card_with_the_papers_own_facts():
    cards = {c.name: c for c in build_summary(confirmed()).medicines}

    assert list(cards) == [
        "furosemide",
        "metoprolol succinate ER",
        "potassium chloride ER",
        "lisinopril",
        "acetaminophen",
        "amlodipine",
    ]
    furosemide = cards["furosemide"]
    assert furosemide.status == "CHANGED" and furosemide.other_names == ["LASIX"]
    assert furosemide.dose == "40 mg" and furosemide.source_page == 1
    assert "once daily" in furosemide.how_often
    assert furosemide.note and "20 mg" in furosemide.note  # the papers' own words on the change


def test_a_stopped_medicine_card_says_to_ask_the_pharmacist():
    card = next(c for c in build_summary(confirmed()).medicines if c.name == "amlodipine")

    assert card.status == "STOPPED"
    assert (
        card.note
        == "Your papers say to stop this medicine. Ask your pharmacist if you are not sure."
    )


def test_an_as_needed_medicine_card_is_marked_as_needed():
    card = next(c for c in build_summary(confirmed()).medicines if c.name == "acetaminophen")

    assert card.as_needed is True


def test_a_continued_medicine_has_no_note_and_the_summary_keeps_its_sections():
    summary = build_summary(confirmed())

    lisinopril = next(c for c in summary.medicines if c.name == "lisinopril")
    assert lisinopril.note is None
    assert lines(summary, "medicines")  # the sentence list is still there for any other reader


def test_the_summary_says_when_the_patient_confirmed():
    from datetime import UTC, datetime

    when = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)

    assert build_summary(confirmed(confirmed_at=when)).confirmed_at == when
