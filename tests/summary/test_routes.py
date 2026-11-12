from collections.abc import Callable

from fastapi.testclient import TestClient
from icalendar import Calendar
from sqlmodel import Session, select

from app.models import PatientAccess, Role, User
from tests.auth.helpers import FakeProvider, sign_in
from tests.documents.test_upload_api import decide_all, owner, upload
from tests.fakes import FakeLLM
from tests.samples import patient1_profile


def urls(patient_id: str) -> list[str]:
    base = f"/patients/{patient_id}"
    return [f"{base}/summary", f"{base}/schedule", f"{base}/schedule.ics"]


def test_the_owner_gets_a_summary_a_schedule_and_a_calendar(
    client: TestClient, confirmed_patient: str
):
    summary = client.get(f"/patients/{confirmed_patient}/summary").json()
    schedule = client.get(f"/patients/{confirmed_patient}/schedule").json()
    calendar = client.get(f"/patients/{confirmed_patient}/schedule.ics")

    assert summary["sections"][0]["key"] == "medicines"
    assert [dose["slot"] for dose in schedule["daily"]] == ["MORNING", "EVENING"]
    assert [m["name"] for m in schedule["stopped"]] == ["amlodipine"]
    assert calendar.headers["content-type"].startswith("text/calendar")
    assert "attachment" in calendar.headers["content-disposition"]
    assert calendar.headers["cache-control"] == "no-store"
    assert len(Calendar.from_ical(calendar.content).walk("VEVENT")) == 3


def test_the_calendar_titles_option_is_checked(client: TestClient, confirmed_patient: str):
    base = f"/patients/{confirmed_patient}/schedule.ics"

    detailed = client.get(base, params={"titles": "detailed"})
    assert b"furosemide" in detailed.content
    assert b"furosemide" not in client.get(base).content
    assert client.get(base, params={"titles": "nonsense"}).status_code == 422


def test_nothing_is_built_from_papers_that_are_not_confirmed_yet(
    client: TestClient, provider: FakeProvider, llm: FakeLLM
):
    patient_id = owner(client, provider)
    llm.queue_extraction(patient1_profile())
    upload(client, patient_id)  # read, but the patient has not confirmed it

    for url in urls(patient_id):
        assert client.get(url).status_code == 404


def test_removed_items_never_reach_the_summary_schedule_or_calendar(
    client: TestClient, provider: FakeProvider, llm: FakeLLM
):
    patient_id = owner(client, provider)
    llm.queue_extraction(patient1_profile())
    upload(client, patient_id)
    extraction = client.get(f"/patients/{patient_id}/extraction").json()
    lisinopril = next(
        i for i in extraction["items"] if i["data"].get("name_as_written") == "lisinopril"
    )
    client.put(
        f"/patients/{patient_id}/profile",
        json=decide_all(extraction, **{lisinopril["id"]: {"action": "remove"}}),
    )

    summary = client.get(f"/patients/{patient_id}/summary").text
    schedule = client.get(f"/patients/{patient_id}/schedule").text
    calendar = client.get(f"/patients/{patient_id}/schedule.ics", params={"titles": "detailed"})

    assert "lisinopril" not in summary + schedule + calendar.text
    assert "furosemide" in summary


def test_a_patients_edit_in_the_confirmation_screen_shows_up(
    client: TestClient, provider: FakeProvider, llm: FakeLLM
):
    patient_id = owner(client, provider)
    llm.queue_extraction(patient1_profile())
    upload(client, patient_id)
    extraction = client.get(f"/patients/{patient_id}/extraction").json()
    furosemide = next(
        i for i in extraction["items"] if i["data"].get("name_as_written") == "furosemide"
    )
    edited = {**furosemide["data"], "dose": "20 mg"}
    client.put(
        f"/patients/{patient_id}/profile",
        json=decide_all(extraction, **{furosemide["id"]: {"data": edited}}),
    )

    summary = client.get(f"/patients/{patient_id}/summary").text
    assert "Now: 20 mg" in summary


def test_an_aide_can_read_all_three(
    client: TestClient,
    new_client: Callable[[], TestClient],
    provider: FakeProvider,
    db: Session,
    confirmed_patient: str,
):
    aide = new_client()
    sign_in(aide, provider, sub="aide", email="aide@example.com")
    aide_user = db.exec(select(User).where(User.google_sub == "aide")).one()
    db.add(PatientAccess(patient_id=confirmed_patient, user_id=aide_user.id, role=Role.AIDE))
    db.commit()

    for url in urls(confirmed_patient):
        assert aide.get(url).status_code == 200


def test_a_stranger_cannot_read_anything_and_patient_ids_cannot_be_probed(
    new_client: Callable[[], TestClient], provider: FakeProvider, confirmed_patient: str
):
    stranger = new_client()
    stranger_patient = owner(stranger, provider, sub="stranger", email="s@example.com")

    for url in urls(confirmed_patient):
        assert stranger.get(url).status_code == 404
    # Their own patient has nothing confirmed, and never shows another patient's data.
    for url in urls(stranger_patient):
        assert stranger.get(url).status_code == 404


def test_signed_out_requests_are_refused(app, confirmed_patient: str):
    anonymous = TestClient(app, follow_redirects=False)
    for url in urls(confirmed_patient):
        assert anonymous.get(url).status_code == 401
