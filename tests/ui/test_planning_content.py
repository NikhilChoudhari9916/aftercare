from ui.api_client import FollowUpLine
from ui.content import (
    PLAN_SAVED,
    build_plan_payload,
    format_day,
    times_note,
    visit_start_state,
    visit_when_text,
)


def visit(**fields) -> FollowUpLine:
    base = {
        "item_id": "v1",
        "what": "Cardiology follow-up",
        "when": "Tuesday, 10/20/2026 at 10:30 a.m.",
        "with_whom": "Dr. Rivera",
        "kind": "booked_time",
        "papers_date": "2026-10-20",
        "papers_time": "10:30",
        "status": None,
        "date": "2026-10-20",
        "time": "10:30",
        "call_on": None,
        "chosen": False,
        "in_calendar": True,
        "source_page": 3,
    }
    return FollowUpLine(**{**base, **fields})


def test_days_read_the_way_people_say_them():
    assert format_day("2026-10-20") == "Tue, Oct 20, 2026"
    assert format_day("2026-11-01") == "Sun, Nov 1, 2026"
    assert format_day(None) == "" and format_day("") == ""
    assert format_day("not a date") == "not a date"


def test_the_times_note_says_how_many_when_the_papers_are_clear():
    assert times_note(2) == "Your papers say 2 times a day, so pick 2."
    assert times_note(1) == "Your papers say 1 time a day, so pick 1."
    assert "don't say a clear time" in times_note(None)


def test_the_form_starts_from_what_the_papers_gave():
    booked = visit_start_state(visit())
    assert booked == {"status": "BOOKED", "date": "2026-10-20", "time": "10:30", "call_on": ""}

    window = visit_start_state(visit(kind="window", papers_time=None, time=None))
    assert (window["status"], window["date"], window["time"]) == ("BOOKED", "2026-10-20", "")

    undated = visit_start_state(
        visit(kind="no_date", papers_date=None, papers_time=None, date=None, time=None)
    )
    assert undated == {"status": "NOT_BOOKED", "date": "", "time": "", "call_on": ""}


def test_the_form_starts_from_the_patients_saved_choice_when_there_is_one():
    saved = visit(chosen=True, status="NOT_BOOKED", date=None, time=None, call_on="2026-11-14")
    assert visit_start_state(saved) == {
        "status": "NOT_BOOKED",
        "date": "",
        "time": "",
        "call_on": "2026-11-14",
    }


def test_the_payload_drops_blank_boxes_and_sends_only_what_each_choice_needs():
    payload = build_plan_payload(
        {"m1": ["07:30", ""], "m2": []},
        {
            "v1": {"status": "BOOKED", "date": "2026-10-20", "time": "", "call_on": "2026-11-14"},
            "v2": {"status": "NOT_BOOKED", "date": "2026-10-21", "time": "09:00", "call_on": ""},
        },
    )

    assert payload == {
        "medicines": [
            {"item_id": "m1", "times": ["07:30"]},
            {"item_id": "m2", "times": []},
        ],
        "visits": [
            {"item_id": "v1", "status": "BOOKED", "date": "2026-10-20", "time": None},
            {"item_id": "v2", "status": "NOT_BOOKED", "call_on": None},
        ],
    }


def test_a_visit_shows_the_patients_choice_or_else_the_papers_words():
    assert visit_when_text(visit()) == "Tuesday, 10/20/2026 at 10:30 a.m., with Dr. Rivera"

    booked = visit(chosen=True, status="BOOKED", date="2026-10-22", time="14:00")
    assert visit_when_text(booked) == "Thu, Oct 22, 2026 at 2:00 PM"
    all_day = visit(chosen=True, status="BOOKED", date="2026-10-22", time=None)
    assert visit_when_text(all_day) == "Thu, Oct 22, 2026 (all day)"

    not_yet = visit(chosen=True, status="NOT_BOOKED", date=None, time=None, call_on="2026-11-14")
    assert visit_when_text(not_yet) == "Not booked yet. Reminder to call on Sat, Nov 14, 2026."
    no_day = visit(chosen=True, status="NOT_BOOKED", date=None, time=None)
    assert visit_when_text(no_day) == "Not booked yet."


def test_the_saved_message_says_the_schedule_and_calendar_follow_the_choice():
    assert "schedule and calendar" in PLAN_SAVED
