from collections.abc import Callable
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from icalendar import Calendar
from sqlmodel import Session, select

from app.models import MedicinePlan, PatientAccess, Role, User, VisitPlan
from tests.auth.helpers import FakeProvider, count, sign_in
from tests.documents.test_upload_api import decide_all, owner, upload
from tests.fakes import FakeLLM
from tests.samples import patient1_profile


def schedule(client: TestClient, patient_id: str) -> dict:
    return client.get(f"/patients/{patient_id}/schedule").json()


def good_plan(current: dict, *, morning="07:30", visit_date="2026-10-20") -> dict:
    """A valid plan built from what the schedule endpoint offered, with the morning time changed."""
    medicines = []
    for line in current["plan_medicines"]:
        times = [morning] if line["suggested_times"] == ["08:00"] else line["suggested_times"]
        medicines.append({"item_id": line["item_id"], "times": times})
    visits = [
        {"item_id": v["item_id"], "status": "BOOKED", "date": visit_date, "time": "10:30"}
        for v in current["follow_ups"]
    ]
    return {"medicines": medicines, "visits": visits}


def test_the_schedule_offers_everything_the_planning_form_needs(
    client: TestClient, confirmed_patient: str
):
    current = schedule(client, confirmed_patient)

    names = [line["name"] for line in current["plan_medicines"]]
    assert names == ["furosemide", "metoprolol succinate ER", "potassium chloride ER", "lisinopril"]
    assert all(line["item_id"] and line["times_needed"] == 1 for line in current["plan_medicines"])
    assert current["follow_ups"][0]["kind"] == "booked_time"
    assert current["follow_ups"][0]["chosen"] is False


def test_the_owner_saves_a_plan_and_the_schedule_and_calendar_follow_it(
    client: TestClient, confirmed_patient: str
):
    plan = good_plan(schedule(client, confirmed_patient))

    saved = client.put(f"/patients/{confirmed_patient}/plan", json=plan)

    assert saved.status_code == 200
    again = schedule(client, confirmed_patient)
    assert [d["time"] for d in again["daily"]] == ["07:30", "18:00"]
    assert all(line["chosen"] for line in again["plan_medicines"])
    assert again["follow_ups"][0]["chosen"] is True
    calendar = client.get(f"/patients/{confirmed_patient}/schedule.ics")
    starts = [str(e["DTSTART"].dt) for e in Calendar.from_ical(calendar.content).walk("VEVENT")]
    assert any("07:30:00" in start for start in starts)


def test_saving_again_replaces_the_old_plan_instead_of_piling_up(
    client: TestClient, confirmed_patient: str, db: Session
):
    current = schedule(client, confirmed_patient)
    client.put(f"/patients/{confirmed_patient}/plan", json=good_plan(current, morning="07:30"))
    client.put(f"/patients/{confirmed_patient}/plan", json=good_plan(current, morning="09:00"))

    assert count(db, MedicinePlan) == 4
    assert count(db, VisitPlan) == 1
    assert [d["time"] for d in schedule(client, confirmed_patient)["daily"]] == ["09:00", "18:00"]


def test_a_plan_the_server_cannot_accept_is_refused_with_a_plain_sentence_and_nothing_is_saved(
    client: TestClient, confirmed_patient: str, db: Session
):
    plan = good_plan(schedule(client, confirmed_patient))
    plan["medicines"][0]["times"] = ["08:00", "20:00"]  # the papers say once a day

    response = client.put(f"/patients/{confirmed_patient}/plan", json=plan)

    assert response.status_code == 422
    assert "1 time" in response.json()["detail"]
    assert count(db, MedicinePlan) == 0


def test_an_incomplete_or_malformed_plan_is_refused(client: TestClient, confirmed_patient: str):
    url = f"/patients/{confirmed_patient}/plan"
    plan = good_plan(schedule(client, confirmed_patient))

    assert (
        client.put(url, json={"medicines": plan["medicines"][:1], "visits": []}).status_code == 422
    )
    assert client.put(url, json={"medicines": "nope"}).status_code == 422
    bad_status = {**plan, "visits": [{**plan["visits"][0], "status": "MAYBE"}]}
    assert client.put(url, json=bad_status).status_code == 422


def test_a_call_reminder_in_the_past_is_refused(client: TestClient, confirmed_patient: str):
    plan = good_plan(schedule(client, confirmed_patient))
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    plan["visits"] = [
        {"item_id": plan["visits"][0]["item_id"], "status": "NOT_BOOKED", "call_on": yesterday}
    ]

    assert client.put(f"/patients/{confirmed_patient}/plan", json=plan).status_code == 422


def test_an_aide_can_read_the_plan_but_not_change_it(
    client: TestClient,
    new_client: Callable[[], TestClient],
    provider: FakeProvider,
    db: Session,
    confirmed_patient: str,
):
    plan = good_plan(schedule(client, confirmed_patient))
    aide = new_client()
    sign_in(aide, provider, sub="aide", email="aide@example.com")
    aide_user = db.exec(select(User).where(User.google_sub == "aide")).one()
    db.add(PatientAccess(patient_id=confirmed_patient, user_id=aide_user.id, role=Role.AIDE))
    db.commit()

    assert aide.put(f"/patients/{confirmed_patient}/plan", json=plan).status_code == 403
    assert aide.get(f"/patients/{confirmed_patient}/schedule").status_code == 200
    assert count(db, MedicinePlan) == 0


def test_a_stranger_cannot_change_another_patients_plan_and_cannot_probe_for_it(
    client: TestClient,
    new_client: Callable[[], TestClient],
    provider: FakeProvider,
    db: Session,
    confirmed_patient: str,
):
    plan = good_plan(schedule(client, confirmed_patient))
    stranger = new_client()
    owner(stranger, provider, sub="stranger", email="s@example.com")

    assert stranger.put(f"/patients/{confirmed_patient}/plan", json=plan).status_code == 404
    assert count(db, MedicinePlan) == 0


def test_one_patients_plan_never_appears_in_anothers_schedule(
    client: TestClient,
    new_client: Callable[[], TestClient],
    provider: FakeProvider,
    llm: FakeLLM,
    confirmed_patient: str,
):
    client.put(
        f"/patients/{confirmed_patient}/plan",
        json=good_plan(schedule(client, confirmed_patient), morning="06:15"),
    )
    other = new_client()
    other_patient = owner(other, provider, sub="other", email="o@example.com")
    llm.queue_extraction(patient1_profile())
    upload(other, other_patient)
    extraction = other.get(f"/patients/{other_patient}/extraction").json()
    other.put(f"/patients/{other_patient}/profile", json=decide_all(extraction))

    theirs = schedule(other, other_patient)

    assert [d["time"] for d in theirs["daily"]] == ["08:00", "18:00"]
    assert not any(line["chosen"] for line in theirs["plan_medicines"])


def test_signed_out_and_unconfirmed_requests_are_refused(
    app, client: TestClient, provider: FakeProvider, llm: FakeLLM, confirmed_patient: str
):
    plan = good_plan(schedule(client, confirmed_patient))
    anonymous = TestClient(app, follow_redirects=False)
    assert anonymous.put(f"/patients/{confirmed_patient}/plan", json=plan).status_code == 401

    # A patient whose papers are read but not yet confirmed has nothing to plan.
    fresh = TestClient(app, follow_redirects=False)
    fresh_patient = owner(fresh, provider, sub="fresh", email="f@example.com")
    llm.queue_extraction(patient1_profile())
    upload(fresh, fresh_patient)
    assert fresh.put(f"/patients/{fresh_patient}/plan", json=plan).status_code == 404


def test_new_confirmed_papers_start_with_a_fresh_plan(
    client: TestClient, llm: FakeLLM, confirmed_patient: str
):
    client.put(
        f"/patients/{confirmed_patient}/plan",
        json=good_plan(schedule(client, confirmed_patient), morning="06:15"),
    )

    llm.queue_extraction(patient1_profile())
    upload(client, confirmed_patient)
    extraction = client.get(f"/patients/{confirmed_patient}/extraction").json()
    client.put(f"/patients/{confirmed_patient}/profile", json=decide_all(extraction))

    after = schedule(client, confirmed_patient)
    assert [d["time"] for d in after["daily"]] == ["08:00", "18:00"]
    assert not any(line["chosen"] for line in after["plan_medicines"])


@pytest.mark.parametrize("titles", ["private", "detailed"])
def test_the_not_booked_call_reminder_reaches_the_calendar_file(
    client: TestClient, confirmed_patient: str, titles: str
):
    plan = good_plan(schedule(client, confirmed_patient))
    call_day = (date.today() + timedelta(days=2)).isoformat()
    plan["visits"] = [
        {"item_id": plan["visits"][0]["item_id"], "status": "NOT_BOOKED", "call_on": call_day}
    ]
    assert client.put(f"/patients/{confirmed_patient}/plan", json=plan).status_code == 200

    ics = client.get(f"/patients/{confirmed_patient}/schedule.ics", params={"titles": titles})
    summaries = [str(e["SUMMARY"]) for e in Calendar.from_ical(ics.content).walk("VEVENT")]

    wanted = "Call to book an appointment" if titles == "private" else "Call to book: Cardiology"
    assert any(s.startswith(wanted) for s in summaries)


def test_a_browser_request_from_another_site_cannot_change_the_plan(
    client: TestClient, confirmed_patient: str, db: Session
):
    plan = good_plan(schedule(client, confirmed_patient))

    response = client.put(
        f"/patients/{confirmed_patient}/plan", json=plan, headers={"origin": "https://evil.example"}
    )

    assert response.status_code == 403
    assert count(db, MedicinePlan) == 0


def test_a_huge_list_of_times_is_refused_without_being_processed(
    client: TestClient, confirmed_patient: str
):
    plan = good_plan(schedule(client, confirmed_patient))
    plan["medicines"][0]["times"] = [f"{i % 24:02d}:{i % 60:02d}" for i in range(50_000)]

    response = client.put(f"/patients/{confirmed_patient}/plan", json=plan)

    assert response.status_code == 422
