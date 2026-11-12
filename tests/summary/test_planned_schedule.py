from datetime import UTC, date, datetime

import pytest
from icalendar import Calendar

from app.extraction.schema import ExtractedFollowUp
from app.models import VisitStatus
from app.summary.calendar_export import build_ics
from app.summary.choices import Plan, VisitChoice
from app.summary.schedule import Slot, build_schedule, part_of_day
from tests.summary.helpers import confirmed, with_medicine

TODAY = date(2026, 11, 12)
NOW = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)


def visit(when: str, what: str = "Checkup") -> ExtractedFollowUp:
    return ExtractedFollowUp(
        what=what, when=when, with_whom="Dr. Rivera", source_quote="q", source_page=3
    )


def events(profile, plan=None, **options):
    ics = build_ics(build_schedule(profile, plan), "patient-1", today=TODAY, now=NOW, **options)
    return list(Calendar.from_ical(ics).walk("VEVENT"))


@pytest.mark.parametrize(
    ("hhmm", "slot"),
    [
        ("05:00", Slot.MORNING),
        ("08:00", Slot.MORNING),
        ("11:59", Slot.MORNING),
        ("12:00", Slot.MIDDAY),
        ("15:30", Slot.MIDDAY),
        ("16:00", Slot.EVENING),
        ("19:59", Slot.EVENING),
        ("20:00", Slot.BEDTIME),
        ("23:30", Slot.BEDTIME),
        ("02:00", Slot.BEDTIME),
    ],
)
def test_a_chosen_time_gets_a_part_of_the_day_name(hhmm, slot):
    assert part_of_day(hhmm) == slot


def test_without_a_plan_the_schedule_uses_the_everyday_defaults():
    schedule = build_schedule(confirmed())

    assert [(d.time, d.label) for d in schedule.daily] == [
        ("08:00", "Morning"),
        ("18:00", "Evening"),
    ]
    furosemide = schedule.plan_medicines[0]
    assert (furosemide.times, furosemide.suggested_times, furosemide.chosen) == (
        ["08:00"],
        ["08:00"],
        False,
    )
    assert furosemide.times_needed == 1
    assert furosemide.item_id == "med-0"


def test_the_patients_times_replace_the_defaults_and_doses_group_by_exact_time():
    plan = Plan(
        medicines={"med-0": ["07:30"], "med-1": ["21:00"], "med-2": ["07:30"], "med-3": ["08:00"]}
    )

    schedule = build_schedule(confirmed(), plan)

    assert [(d.time, d.label, [m.name for m in d.medicines]) for d in schedule.daily] == [
        ("07:30", "Morning", ["furosemide", "potassium chloride ER"]),
        ("08:00", "Morning", ["lisinopril"]),
        ("21:00", "Bedtime", ["metoprolol succinate ER"]),
    ]
    assert schedule.plan_medicines[0].chosen is True


def test_a_medicine_with_unclear_timing_joins_the_schedule_once_the_patient_picks_times():
    profile = with_medicine("every 6 hours")
    assert [m.name for m in build_schedule(profile).needs_timing] == ["testol"]

    schedule = build_schedule(profile, Plan(medicines={"med-0": ["06:00", "12:00", "18:00"]}))

    assert schedule.needs_timing == []
    assert [d.time for d in schedule.daily] == ["06:00", "12:00", "18:00"]


def test_choosing_no_times_leaves_an_unclear_medicine_in_the_to_choose_list():
    schedule = build_schedule(with_medicine("every 6 hours"), Plan(medicines={"med-0": []}))
    assert [m.name for m in schedule.needs_timing] == ["testol"]
    assert schedule.daily == []


def test_a_plan_for_a_medicine_that_is_not_scheduled_is_never_used():
    # acetaminophen is as needed, amlodipine is stopped
    plan = Plan(medicines={"med-4": ["09:00"], "med-5": ["09:00"]})
    schedule = build_schedule(confirmed(), plan)
    assert "09:00" not in [d.time for d in schedule.daily]


@pytest.mark.parametrize(
    ("when", "kind", "papers_time"),
    [
        ("Tuesday, 10/20/2026 at 10:30 a.m.", "booked_time", "10:30"),
        ("October 21, 2026", "date_only", None),
        ("Monday, 10/19/2026, any time 7 a.m. to 4 p.m.", "window", None),
        ("within 7 days of discharge (please call to schedule)", "no_date", None),
    ],
)
def test_each_visit_is_sorted_by_what_the_papers_gave(when, kind, papers_time):
    line = build_schedule(confirmed(follow_ups=[visit(when)])).follow_ups[0]

    assert line.kind == kind
    assert line.papers_time == papers_time
    assert (line.status, line.chosen) == (None, False)


def test_a_booked_choice_overrides_the_papers_date_and_time():
    choice = VisitChoice(status=VisitStatus.BOOKED, date=date(2026, 10, 22), time="14:00")
    plan = Plan(visits={"visit-0": choice})

    line = build_schedule(confirmed(), plan).follow_ups[0]

    assert (line.date, line.time, line.status, line.chosen) == (
        date(2026, 10, 22),
        "14:00",
        VisitStatus.BOOKED,
        True,
    )
    assert line.papers_date == date(2026, 10, 20)  # the papers' words are untouched


def test_a_not_booked_choice_has_no_visit_date_and_is_in_the_calendar_only_with_a_call_day():
    papers = visit("within 7 days of discharge")
    profile = confirmed(follow_ups=[papers])

    no_day = Plan(visits={"visit-0": VisitChoice(status=VisitStatus.NOT_BOOKED)})
    assert build_schedule(profile, no_day).follow_ups[0].in_calendar is False

    with_day = Plan(
        visits={"visit-0": VisitChoice(status=VisitStatus.NOT_BOOKED, call_on=date(2026, 11, 14))}
    )
    line = build_schedule(profile, with_day).follow_ups[0]
    assert (line.date, line.call_on, line.in_calendar) == (None, date(2026, 11, 14), True)


# --- the calendar file ---


def test_the_calendar_uses_the_patients_times():
    plan = Plan(
        medicines={"med-0": ["07:30"], "med-1": ["21:00"], "med-2": ["07:30"], "med-3": ["07:30"]}
    )

    found = {str(e["SUMMARY"]): e["DTSTART"].dt for e in events(confirmed(follow_ups=[]), plan)}

    assert found == {
        "Morning medicines": datetime(2026, 11, 12, 7, 30),
        "Bedtime medicines": datetime(2026, 11, 12, 21, 0),
    }


def test_two_medicines_at_different_chosen_times_get_separate_events():
    profile = confirmed(follow_ups=[], medicines=confirmed().medicines[:2])
    plan = Plan(medicines={"med-0": ["07:30"], "med-1": ["09:15"]})

    starts = sorted(e["DTSTART"].dt for e in events(profile, plan))

    assert starts == [datetime(2026, 11, 12, 7, 30), datetime(2026, 11, 12, 9, 15)]


def test_a_call_to_book_reminder_is_an_all_day_entry_on_the_chosen_day():
    plan = Plan(
        visits={"visit-0": VisitChoice(status=VisitStatus.NOT_BOOKED, call_on=date(2026, 11, 14))}
    )
    profile = confirmed(follow_ups=[visit("within 7 days of discharge", "Primary care follow-up")])

    private = events(profile, plan)
    detailed = events(profile, plan, titles="detailed")

    reminder = next(e for e in private if "Call" in str(e["SUMMARY"]))
    assert str(reminder["SUMMARY"]) == "Call to book an appointment"
    assert reminder["DTSTART"].dt == date(2026, 11, 14)
    assert reminder["DTEND"].dt == date(2026, 11, 15)
    assert any(str(e["SUMMARY"]) == "Call to book: Primary care follow-up" for e in detailed)


def test_a_visit_not_booked_with_no_call_day_makes_no_entry():
    plan = Plan(visits={"visit-0": VisitChoice(status=VisitStatus.NOT_BOOKED)})
    found = events(confirmed(follow_ups=[visit("within 7 days")]), plan)
    assert [
        e for e in found if "Call" in str(e["SUMMARY"]) or "appointment" in str(e["SUMMARY"])
    ] == []


def test_a_booked_choice_decides_the_visit_entry_not_the_papers():
    plan = Plan(
        visits={
            "visit-0": VisitChoice(status=VisitStatus.BOOKED, date=date(2026, 10, 22), time=None)
        }
    )
    found = events(confirmed(), plan)

    appointment = next(e for e in found if str(e["SUMMARY"]) == "Medical appointment")
    assert appointment["DTSTART"].dt == date(2026, 10, 22)  # all day: no time was chosen
    assert str(appointment["DTEND"].dt) == "2026-10-23"


def test_a_planned_detailed_visit_says_it_was_planned_by_the_patient():
    plan = Plan(
        visits={
            "visit-0": VisitChoice(status=VisitStatus.BOOKED, date=date(2026, 10, 22), time="14:00")
        }
    )
    found = events(confirmed(), plan, titles="detailed")

    visit_event = next(e for e in found if "Cardiology" in str(e["SUMMARY"]))
    assert "planned this in AfterCare" in str(visit_event["DESCRIPTION"])
    assert "papers say" not in str(visit_event["DESCRIPTION"]).lower()
