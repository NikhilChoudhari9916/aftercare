from datetime import date

import pytest

from app.models import VisitStatus
from app.summary.plan import PlanError, PlanIn, validate_plan
from tests.summary.helpers import confirmed, with_medicine

TODAY = date(2026, 11, 12)


def meds(**times: list[str]) -> list[dict]:
    """Times for Patient 1's four scheduled medicines, med-0 to med-3, with any overrides."""
    base = {
        "med-0": ["08:00"],
        "med-1": ["18:00"],
        "med-2": ["08:00"],
        "med-3": ["08:00"],
    }
    base.update({key.replace("_", "-"): value for key, value in times.items()})
    return [{"item_id": key, "times": value} for key, value in base.items()]


def visits(**changes) -> list[dict]:
    entry = {"item_id": "visit-0", "status": "BOOKED", "date": "2026-10-20", "time": "10:30"}
    entry.update(changes)
    return [entry]


def check(profile=None, *, medicines=None, visit_entries=None):
    plan = PlanIn(
        medicines=medicines if medicines is not None else meds(),
        visits=visit_entries if visit_entries is not None else visits(),
    )
    return validate_plan(profile or confirmed(), plan, today=TODAY)


def test_a_good_plan_is_accepted_and_times_are_sorted():
    plan = check(medicines=meds(med_0=["07:30"]))

    assert plan.medicines["med-0"] == ["07:30"]
    assert plan.visits["visit-0"].date == date(2026, 10, 20)
    assert plan.visits["visit-0"].time == "10:30"


def test_every_scheduled_medicine_and_every_visit_must_be_covered():
    with pytest.raises(PlanError, match="every medicine"):
        check(medicines=meds()[:-1])
    with pytest.raises(PlanError, match="every visit"):
        check(visit_entries=[])


def test_stopped_and_as_needed_medicines_cannot_be_given_times():
    # med-4 is acetaminophen (as needed) and med-5 is amlodipine (stopped)
    with pytest.raises(PlanError, match="every medicine"):
        check(medicines=[*meds(), {"item_id": "med-4", "times": ["09:00"]}])
    with pytest.raises(PlanError, match="every medicine"):
        check(medicines=[*meds(), {"item_id": "med-5", "times": ["09:00"]}])


def test_an_id_that_is_not_in_these_papers_is_refused():
    with pytest.raises(PlanError):
        check(medicines=[*meds(), {"item_id": "someone-elses-item", "times": ["09:00"]}])
    with pytest.raises(PlanError):
        check(visit_entries=visits(item_id="someone-elses-visit"))


def test_the_number_of_times_must_match_what_the_papers_clearly_say():
    with pytest.raises(PlanError, match="1 time"):
        check(medicines=meds(med_0=["08:00", "20:00"]))
    with pytest.raises(PlanError, match="1 time"):
        check(medicines=meds(med_0=[]))


def test_twice_a_day_needs_exactly_two_times():
    profile = with_medicine("twice a day")
    ok = validate_plan(
        profile,
        PlanIn(medicines=[{"item_id": "med-0", "times": ["08:00", "20:00"]}], visits=[]),
        today=TODAY,
    )
    assert ok.medicines["med-0"] == ["08:00", "20:00"]
    with pytest.raises(PlanError, match="2 time"):
        validate_plan(
            profile,
            PlanIn(medicines=[{"item_id": "med-0", "times": ["08:00"]}], visits=[]),
            today=TODAY,
        )


def test_when_the_papers_are_unclear_the_patient_decides_how_many_up_to_six():
    profile = with_medicine("every 6 hours")

    def plan(times):
        return PlanIn(medicines=[{"item_id": "med-0", "times": times}], visits=[])

    assert validate_plan(profile, plan([]), today=TODAY).medicines["med-0"] == []
    four = ["06:00", "12:00", "18:00", "23:30"]
    assert validate_plan(profile, plan(four), today=TODAY).medicines["med-0"] == four
    with pytest.raises(PlanError, match="at most 6"):
        validate_plan(profile, plan([f"0{i}:00" for i in range(7)]), today=TODAY)


@pytest.mark.parametrize("bad", ["8:30", "25:00", "08:60", "noon", "", "08:00 AM"])
def test_a_time_must_be_a_real_24_hour_clock_time(bad):
    with pytest.raises(PlanError, match="pick a time"):
        check(medicines=meds(med_0=[bad]))


def test_the_same_time_twice_is_refused():
    profile = with_medicine("every 6 hours")
    with pytest.raises(PlanError, match="different time"):
        validate_plan(
            profile,
            PlanIn(medicines=[{"item_id": "med-0", "times": ["08:00", "08:00"]}], visits=[]),
            today=TODAY,
        )


def test_a_booked_visit_needs_a_date_and_may_skip_the_time():
    plan = check(visit_entries=visits(time=None))
    assert plan.visits["visit-0"].time is None

    with pytest.raises(PlanError, match="date of the visit"):
        check(visit_entries=visits(date=None))


def test_a_booked_visit_does_not_take_a_call_reminder():
    with pytest.raises(PlanError, match="does not need a reminder"):
        check(visit_entries=visits(call_on="2026-11-14"))


def test_a_visit_not_booked_yet_may_have_a_call_reminder_today_or_later():
    entry = {"item_id": "visit-0", "status": "NOT_BOOKED", "call_on": "2026-11-12"}
    plan = check(visit_entries=[entry])
    assert plan.visits["visit-0"].status == VisitStatus.NOT_BOOKED
    assert plan.visits["visit-0"].call_on == TODAY

    plan = check(visit_entries=[{"item_id": "visit-0", "status": "NOT_BOOKED"}])
    assert plan.visits["visit-0"].call_on is None

    with pytest.raises(PlanError, match="today or a later day"):
        check(visit_entries=[{**entry, "call_on": "2026-11-11"}])


def test_a_visit_not_booked_yet_cannot_also_have_a_date_or_time():
    with pytest.raises(PlanError, match="booked if you have a date"):
        check(visit_entries=[{"item_id": "visit-0", "status": "NOT_BOOKED", "date": "2026-11-20"}])
    with pytest.raises(PlanError, match="booked if you have a date"):
        check(visit_entries=[{"item_id": "visit-0", "status": "NOT_BOOKED", "time": "09:00"}])


def test_a_date_must_look_like_a_real_year():
    with pytest.raises(PlanError, match="does not look right"):
        check(visit_entries=visits(date="1999-01-01"))
    with pytest.raises(PlanError, match="does not look right"):
        check(visit_entries=visits(date="2201-01-01"))


def test_a_booked_visit_in_the_past_is_allowed_because_the_papers_may_say_so():
    assert check(visit_entries=visits(date="2026-10-20")).visits["visit-0"].date.year == 2026
