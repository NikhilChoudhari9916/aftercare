from app.extraction.schema import MedStatus
from app.qa.profile_text import render_profile_text
from tests.summary.helpers import confirmed, with_medicine


def lines(text: str) -> list[str]:
    return text.splitlines()


def test_each_medicine_has_its_names_dose_timing_and_status():
    text = render_profile_text(confirmed())

    assert "Medicines (confirmed by patient):" in text
    assert (
        "1. furosemide 40 mg | also known as: LASIX | once daily in the morning"
        " | CHANGED: Previously 20 mg once daily."
    ) in lines(text)
    assert (
        "5. acetaminophen 500 mg | also known as: TYLENOL | every 6 hours as needed | AS NEEDED"
    ) in lines(text)
    assert "6. amlodipine 5 mg | also known as: NORVASC | STOPPED" in lines(text)


def test_a_change_note_that_only_repeats_the_status_is_left_out():
    profile = with_medicine("daily", status=MedStatus.NEW, change_note="NEW")

    assert "1. testol 10 mg | daily | NEW" in lines(render_profile_text(profile))


def test_the_discharge_date_is_written_in_words():
    assert "Discharged: October 12, 2026" in render_profile_text(confirmed())


def test_warning_signs_are_grouped_by_who_to_call():
    text = render_profile_text(confirmed())

    assert "- CALL CARE TEAM: Gain more than 2 pounds in one day or 5 pounds in one week" in text
    assert "- CALL 911: Chest pain, severe shortness of breath" in text
    assert text.index("CALL CARE TEAM") < text.index("CALL 911")


def test_follow_ups_and_the_care_team_are_included():
    text = render_profile_text(confirmed())

    assert "- Cardiology follow-up: Tuesday, 10/20/2026 at 10:30 a.m. (A. Rivera, MD)" in text
    assert "Care team: " in text


def test_a_profile_with_no_medicines_says_so():
    text = render_profile_text(confirmed(medicines=[], follow_ups=[]))

    assert "(none)" in text
    assert "Follow-up visits" not in text
