from datetime import UTC, date, datetime

from icalendar import Calendar

from app.extraction.schema import MedStatus
from app.summary.calendar_export import REMINDER_DAYS, build_ics
from app.summary.schedule import build_schedule
from tests.summary.helpers import confirmed, with_medicine

TODAY = date(2026, 11, 12)
NOW = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)


def events(profile, **options):
    ics = build_ics(build_schedule(profile), "patient-1", today=TODAY, now=NOW, **options)
    return list(Calendar.from_ical(ics).walk("VEVENT")), ics.decode()


def titles(found):
    return sorted(str(event["SUMMARY"]) for event in found)


def test_titles_are_private_by_default_and_hold_no_medicine_names():
    found, text = events(confirmed())

    assert titles(found) == ["Evening medicines", "Medical appointment", "Morning medicines"]
    for name in ("furosemide", "metoprolol", "lisinopril", "Rivera", "Cardiology"):
        assert name.lower() not in text.lower()


def test_detailed_titles_name_the_medicines_and_the_visit():
    found, _ = events(confirmed(), titles="detailed")

    assert titles(found) == [
        "Cardiology follow-up with A. Rivera, MD",
        "Evening: metoprolol succinate ER 25 mg",
        "Morning: furosemide 40 mg, potassium chloride ER 20 mEq, lisinopril 10 mg",
    ]


def test_stopped_and_as_needed_medicines_make_no_events():
    only_those = confirmed(
        medicines=[
            m for m in confirmed().medicines if m.status in (MedStatus.STOPPED, MedStatus.AS_NEEDED)
        ],
        follow_ups=[],
    )
    found, _ = events(only_those)
    assert found == []


def test_times_are_local_with_no_time_zone_attached():
    found, text = events(confirmed())
    morning = next(e for e in found if str(e["SUMMARY"]).startswith("Morning"))

    assert morning["DTSTART"].dt == datetime(2026, 11, 12, 8, 0)
    assert morning["DTSTART"].dt.tzinfo is None
    assert "TZID" not in text


def test_daily_reminders_repeat_for_thirty_days_from_today():
    found, _ = events(confirmed())
    morning = next(e for e in found if str(e["SUMMARY"]).startswith("Morning"))
    assert morning["RRULE"]["COUNT"] == [REMINDER_DAYS]


def test_reminders_wait_for_a_discharge_date_that_is_still_ahead():
    found, _ = events(confirmed(), discharge_date=date(2026, 11, 20))
    morning = next(e for e in found if str(e["SUMMARY"]).startswith("Morning"))
    assert morning["DTSTART"].dt.date() == date(2026, 11, 20)


def test_a_fixed_course_stops_on_its_end_date():
    profile = with_medicine("once daily in the morning", end_date="2026-11-16")
    found, _ = events(profile)
    assert found[0]["RRULE"]["COUNT"] == [5]  # Nov 12 to Nov 16, both days included


def test_a_course_that_already_ended_makes_no_event():
    profile = with_medicine("once daily in the morning", end_date="2026-11-01")
    found, _ = events(profile)
    assert found == []


def test_medicines_with_different_end_dates_get_separate_events():
    base = with_medicine("once daily in the morning").medicines[0]
    short = base.model_copy(update={"name_as_written": "short", "end_date": "2026-11-14"})
    long = base.model_copy(update={"name_as_written": "long"})
    found, _ = events(confirmed(medicines=[short, long], follow_ups=[]))

    assert sorted(e["RRULE"]["COUNT"][0] for e in found) == [3, REMINDER_DAYS]


def test_a_visit_with_a_time_is_a_one_hour_event_and_without_one_is_all_day():
    profile = confirmed()
    timed = profile.follow_ups[0]
    dated_only = timed.model_copy(update={"when": "October 21, 2026"})
    unparseable = timed.model_copy(update={"when": "within 7 days of discharge"})
    found, _ = events(confirmed(follow_ups=[timed, dated_only, unparseable]))
    visits = [e for e in found if str(e["SUMMARY"]) == "Medical appointment"]

    assert len(visits) == 2  # the vague one is left for the patient to add by hand
    by_start = {e["DTSTART"].dt: e for e in visits}
    timed_event = by_start[datetime(2026, 10, 20, 10, 30)]
    assert timed_event["DTEND"].dt == datetime(2026, 10, 20, 11, 30)
    assert date(2026, 10, 21) in by_start


def test_events_have_stable_ids_that_do_not_contain_the_patient_id():
    first, text = events(confirmed())
    second, _ = events(confirmed())

    assert sorted(str(e["UID"]) for e in first) == sorted(str(e["UID"]) for e in second)
    assert "patient-1" not in text


def test_the_sequence_number_follows_the_profile_version_so_new_files_update_old_events():
    found, _ = events(confirmed(version=3))
    assert {int(e["SEQUENCE"]) for e in found} == {3}


def test_every_event_has_a_reminder_alert():
    found, _ = events(confirmed())
    assert all(len(e.walk("VALARM")) == 1 for e in found)
