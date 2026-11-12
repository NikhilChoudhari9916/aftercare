from datetime import date, time

import pytest

from app.extraction.schema import ExtractedFollowUp, MedStatus
from app.summary.schedule import (
    Slot,
    build_schedule,
    follow_up_line,
    parse_follow_up_date,
    parse_follow_up_time,
    parse_slots,
)
from tests.summary.helpers import confirmed, with_medicine


@pytest.mark.parametrize(
    ("frequency", "timing", "expected"),
    [
        ("once daily in the morning", None, [Slot.MORNING]),
        ("once daily in the evening", None, [Slot.EVENING]),
        ("once daily with breakfast", None, [Slot.MORNING]),
        ("once a day", "at bedtime", [Slot.BEDTIME]),
        ("every morning", None, [Slot.MORNING]),
        ("at bedtime", None, [Slot.BEDTIME]),
        ("twice a day", None, [Slot.MORNING, Slot.EVENING]),
        ("twice daily", "morning and bedtime", [Slot.MORNING, Slot.BEDTIME]),
        ("every 12 hours", None, [Slot.MORNING, Slot.EVENING]),
        ("three times a day", "with meals", [Slot.MORNING, Slot.MIDDAY, Slot.EVENING]),
        ("every 8 hours", None, [Slot.MORNING, Slot.MIDDAY, Slot.EVENING]),
        ("four times a day", None, [Slot.MORNING, Slot.MIDDAY, Slot.EVENING, Slot.BEDTIME]),
    ],
)
def test_clear_frequencies_become_times_of_day(frequency, timing, expected):
    assert parse_slots(frequency, timing) == expected


@pytest.mark.parametrize(
    ("frequency", "timing"),
    [
        (None, None),
        ("", ""),
        ("once daily", None),  # no time of day written, so the patient chooses
        ("every 6 hours", None),
        ("every other day", "morning"),
        ("once weekly", "morning"),
        ("every 3 days", None),
        ("once daily", "morning and evening"),  # the papers contradict themselves
        ("take as directed", None),
    ],
)
def test_unclear_frequencies_are_never_guessed(frequency, timing):
    assert parse_slots(frequency, timing) is None


def test_patient_one_schedule_matches_the_papers():
    schedule = build_schedule(confirmed())

    times = {dose.slot: [m.name for m in dose.medicines] for dose in schedule.daily}
    assert times == {
        Slot.MORNING: ["furosemide", "potassium chloride ER", "lisinopril"],
        Slot.EVENING: ["metoprolol succinate ER"],
    }
    assert [m.name for m in schedule.stopped] == ["amlodipine"]
    assert [m.name for m in schedule.as_needed] == ["acetaminophen"]
    assert schedule.needs_timing == []


def test_stopped_and_as_needed_medicines_are_never_on_the_daily_schedule():
    for status, flag in ((MedStatus.STOPPED, False), (MedStatus.AS_NEEDED, True)):
        schedule = build_schedule(
            with_medicine("once daily in the morning", status=status, as_needed=flag)
        )
        assert schedule.daily == []


def test_as_needed_words_win_even_when_the_status_says_otherwise():
    schedule = build_schedule(with_medicine("every 6 hours as needed", status=MedStatus.NEW))
    assert [m.name for m in schedule.as_needed] == ["testol"]
    assert schedule.daily == []


def test_unrecognized_frequency_is_shown_as_written_and_the_patient_is_asked():
    schedule = build_schedule(with_medicine("every 6 hours", timing="with water"))

    assert schedule.daily == []
    [line] = schedule.needs_timing
    assert line.how_often == "every 6 hours with water"


def test_an_end_date_is_carried_and_a_bad_one_is_ignored():
    good = build_schedule(with_medicine("once daily in the morning", end_date="2026-11-20"))
    assert good.daily[0].medicines[0].end_date == date(2026, 11, 20)

    bad = build_schedule(with_medicine("once daily in the morning", end_date="soon"))
    assert bad.daily[0].medicines[0].end_date is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Tuesday, 10/20/2026 at 10:30 a.m.", date(2026, 10, 20)),
        ("2026-10-19", date(2026, 10, 19)),
        ("October 20, 2026", date(2026, 10, 20)),
        ("Oct 20th, 2026 at noon", date(2026, 10, 20)),
        ("Sept. 3, 2026", date(2026, 9, 3)),
        ("within 7 days of discharge", None),
        ("next week", None),
        ("13/45/2026", None),  # not a real date
        ("February 30, 2026", None),
    ],
)
def test_follow_up_dates_are_read_only_when_written_out_in_full(text, expected):
    assert parse_follow_up_date(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("at 10:30 a.m.", time(10, 30)),
        ("3 pm", time(15, 0)),
        ("12:15 p.m.", time(12, 15)),
        ("12 a.m.", time(0, 0)),
        ("10:30", None),  # no a.m. or p.m., so it stays an all-day entry
        ("on 10/20/2026", None),
    ],
)
def test_follow_up_times_need_am_or_pm(text, expected):
    assert parse_follow_up_time(text) == expected


def test_follow_up_line_marks_what_can_go_into_a_calendar():
    dated = follow_up_line(
        ExtractedFollowUp(
            what="Cardiology",
            when="Tuesday, 10/20/2026 at 10:30 a.m.",
            with_whom="Dr. Rivera",
            source_quote="q",
            source_page=3,
        )
    )
    assert (dated.date, dated.time, dated.in_calendar) == (date(2026, 10, 20), "10:30", True)

    vague = follow_up_line(
        ExtractedFollowUp(
            what="Primary care",
            when="within 7 days of discharge",
            with_whom=None,
            source_quote="q",
            source_page=3,
        )
    )
    assert (vague.date, vague.time, vague.in_calendar) == (None, None, False)
    assert vague.when == "within 7 days of discharge"
