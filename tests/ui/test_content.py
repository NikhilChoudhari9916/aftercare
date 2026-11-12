import pytest

from ui.api_client import Me, PatientRef, UserInfo
from ui.content import (
    GENERIC_SIGN_IN_ERROR,
    also_called,
    apply_edits,
    calendar_url,
    clock_label,
    describe_role,
    dev_sign_in_form,
    end_date_note,
    error_message,
    injection_warning,
    item_chip,
    item_headline,
    item_lines,
    medicine_title,
    quote_note,
    sign_in_url,
    sign_out_form,
    step_states,
    visit_when,
)


def me_with(*roles: str) -> Me:
    return Me(
        user=UserInfo(id="u", email="a@example.com", display_name="Ada"),
        patients=[PatientRef(id=f"p{i}", role=role) for i, role in enumerate(roles)],
    )


def test_known_error_codes_get_a_friendly_sentence():
    assert "couldn't sign you in" in error_message("sign_in_failed")
    assert "isn't verified" in error_message("email_not_verified")


@pytest.mark.parametrize("code", [None, ""])
def test_no_error_means_no_message(code):
    assert error_message(code) is None


def test_an_unknown_code_gets_the_generic_message_and_is_never_repeated():
    message = error_message("<script>alert(1)</script>")
    assert message == GENERIC_SIGN_IN_ERROR
    assert "script" not in message


@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        (("OWNER",), "You are signed in as the patient."),
        (("AIDE",), "You are signed in as an aide."),
        (("OWNER", "AIDE"), "You are signed in as the patient."),
        ((), "You are signed in."),
    ],
)
def test_the_role_is_described_in_plain_words(roles, expected):
    assert describe_role(me_with(*roles)) == expected


def test_sign_in_goes_to_the_backend_and_returns_to_the_home_page():
    assert sign_in_url("http://localhost:8000") == "http://localhost:8000/auth/login?next=/"


def test_the_sign_out_form_posts_to_the_backend():
    html = sign_out_form("http://localhost:8000")
    assert 'method="post"' in html
    assert 'action="http://localhost:8000/auth/logout"' in html
    assert 'class="ac-nbtn"' in html  # its 48px+ tap size comes from theme.CSS (tested there)


def test_the_sign_out_form_escapes_the_address():
    html = sign_out_form('http://x.test/"><script>alert(1)</script>')
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_the_test_login_form_posts_the_chosen_person_to_the_backend():
    html = dev_sign_in_form("http://localhost:8000", "alex", "Test patient Alex")

    assert 'action="http://localhost:8000/auth/dev-login"' in html
    assert 'name="persona" value="alex"' in html
    assert "Test patient Alex" in html


def test_the_test_login_form_escapes_what_it_is_given():
    html = dev_sign_in_form('http://x/"><script>', 'a"><b>', "<i>label</i>")

    assert "<script>" not in html
    assert "<b>" not in html
    assert "<i>" not in html


MEDICINE = {
    "name_as_written": "furosemide",
    "dose": "40 mg",
    "frequency": "once daily",
    "timing": None,
    "status": "CHANGED",
    "change_note": "Previously 20 mg.",
    "end_date": "2026-11-01",
}


def test_a_medicine_is_headlined_by_name_and_dose_and_described_in_plain_words():
    assert item_headline("medicines", MEDICINE) == "furosemide 40 mg"
    assert item_lines("medicines", MEDICINE) == [
        "once daily",
        "Previously 20 mg.",
        "Last day: 2026-11-01",
    ]


def test_a_medicine_without_a_dose_is_headlined_by_name_only():
    assert (
        item_headline("medicines", {"name_as_written": "lisinopril", "dose": None}) == "lisinopril"
    )


def test_other_sections_read_in_plain_words():
    assert item_headline("follow_ups", {"what": "Cardiology visit"}) == "Cardiology visit"
    assert item_headline("care_team", {"name": "Nurse Line"}) == "Nurse Line"
    assert item_headline("diet_limits", {"text": "Limit salt"}) == "Limit salt"
    assert item_lines("warning_signs", {"text": "x", "tier": "CALL_911"}) == []
    assert item_lines("follow_ups", {"when": "Tuesday", "with_whom": None}) == ["Tuesday"]
    assert item_lines("care_team", {"phone": "555", "hours": "9 to 5"}) == ["555", "9 to 5"]
    assert item_lines("diet_limits", {"text": "Limit salt"}) == []


def test_only_words_that_could_not_be_found_get_a_warning():
    assert quote_note("not_found")
    assert quote_note("verified") is None
    assert quote_note("page_corrected") is None


def test_text_aimed_at_a_program_is_reported_by_page_once():
    assert injection_warning([]) is None
    warning = injection_warning([3, 1, 3])
    assert "Page 1, 3 " in warning


def test_unchanged_edits_change_nothing():
    assert apply_edits(MEDICINE, {"dose": "40 mg", "frequency": "once daily"}) is None


def test_an_edit_changes_only_what_was_typed_and_trims_spaces():
    changed = apply_edits(MEDICINE, {"dose": "  20 mg ", "frequency": "once daily"})
    assert changed["dose"] == "20 mg"
    assert changed["frequency"] == "once daily"
    assert MEDICINE["dose"] == "40 mg"  # the original is not modified


def test_a_blank_answer_clears_an_optional_field_but_not_a_required_one():
    assert apply_edits(MEDICINE, {"change_note": "  "})["change_note"] is None
    follow_up = {"what": "Visit", "when": "Tuesday", "with_whom": "Dr. Rivera"}
    assert apply_edits(follow_up, {"what": ""}) is None
    assert apply_edits(follow_up, {"with_whom": ""})["with_whom"] is None


def test_a_medicine_status_and_a_warning_urgency_become_chips_with_words():
    assert item_chip("medicines", MEDICINE) == ("Changed", "CHANGED")
    assert item_chip("medicines", {"status": "AS_NEEDED"}) == ("Only when needed", "AS_NEEDED")
    assert item_chip("warning_signs", {"tier": "CALL_911"}) == ("Call 911", "CALL_911")
    assert item_chip("warning_signs", {"tier": "CALL_CARE_TEAM"}) == (
        "Call your care team",
        "CALL_CARE_TEAM",
    )


def test_other_items_and_unknown_values_get_no_chip():
    assert item_chip("diet_limits", {"text": "Limit salt"}) is None
    assert item_chip("medicines", {"status": "SOMETHING_NEW"}) is None
    assert item_chip("medicines", {}) is None


def test_the_reading_steps_move_from_pending_to_active_to_done():
    assert step_states("QUEUED", None) == ["active", "pending", "pending", "pending"]
    assert step_states("RUNNING", "ingest") == ["done", "active", "pending", "pending"]
    assert step_states("RUNNING", "check_quotes") == ["done", "done", "done", "active"]
    assert step_states("RUNNING", "normalize") == ["done"] * 4
    assert step_states("SUCCEEDED", "done") == ["done"] * 4
    assert step_states("RUNNING", "something_new") == ["active", "pending", "pending", "pending"]


def test_clock_times_read_the_way_people_say_them():
    assert [clock_label(t) for t in ("08:00", "13:00", "18:00", "21:00", "00:30", "12:00")] == [
        "8:00 AM",
        "1:00 PM",
        "6:00 PM",
        "9:00 PM",
        "12:30 AM",
        "12:00 PM",
    ]


def test_the_calendar_link_points_at_the_backend_and_names_the_title_style():
    base = "http://backend.test/patients/p1/schedule.ics"
    assert calendar_url("http://backend.test", "p1") == f"{base}?titles=private"
    assert calendar_url("http://backend.test", "p1", "detailed") == f"{base}?titles=detailed"


def test_medicine_lines_are_built_from_what_the_papers_gave():
    assert medicine_title("furosemide", "40 mg") == "furosemide 40 mg"
    assert medicine_title("furosemide", None) == "furosemide"
    assert also_called(["LASIX", ""]) == "Also called LASIX"
    assert also_called([]) is None
    assert end_date_note("2026-11-20") == "Until Nov 20, 2026"
    assert end_date_note(None) is None
    assert end_date_note("soon") is None
    assert visit_when("10/20/2026", "Dr. Rivera") == "10/20/2026, with Dr. Rivera"
    assert visit_when("within 7 days", None) == "within 7 days"
