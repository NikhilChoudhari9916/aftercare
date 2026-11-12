from collections.abc import Callable
from datetime import timedelta
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.dependencies import require_access
from app.models import (
    AccessEvent,
    AccessEventKind,
    AccessStatus,
    Patient,
    PatientAccess,
    Role,
    User,
    new_id,
    utc_now,
)
from tests.auth.helpers import BACKEND_URL, UI_URL, FakeProvider, sign_in


@pytest.fixture
def owner_only_app(app: FastAPI) -> FastAPI:
    @app.get("/patients/{patient_id}/owner-thing")
    def owner_thing(access: Annotated[PatientAccess, Depends(require_access(Role.OWNER))]):
        return {"role": access.role}

    @app.get("/patients/{patient_id}/shared-thing")
    def shared_thing(
        access: Annotated[PatientAccess, Depends(require_access(Role.OWNER, Role.AIDE))],
    ):
        return {"role": access.role}

    return app


@pytest.fixture
def owner(owner_only_app: FastAPI, provider: FakeProvider, db: Session) -> tuple[TestClient, str]:
    client = TestClient(owner_only_app, follow_redirects=False)
    sign_in(client, provider, sub="owner-sub", email="owner@example.com")
    return client, client.get("/me").json()["patients"][0]["id"]


@pytest.fixture
def second_person(
    owner_only_app: FastAPI, provider: FakeProvider, db: Session
) -> tuple[TestClient, User]:
    client = TestClient(owner_only_app, follow_redirects=False)
    sign_in(client, provider, sub="other-sub", email="other@example.com")
    return client, db.exec(select(User).where(User.google_sub == "other-sub")).one()


def grant(db: Session, patient_id: str, user: User, **fields) -> PatientAccess:
    access = PatientAccess(patient_id=patient_id, user_id=user.id, **fields)
    db.add(access)
    db.commit()
    return access


def denied_events(db: Session) -> list[AccessEvent]:
    return list(db.exec(select(AccessEvent).where(AccessEvent.kind == AccessEventKind.DENIED)))


def test_the_owner_gets_in(owner: tuple[TestClient, str]):
    client, patient_id = owner
    response = client.get(f"/patients/{patient_id}/owner-thing")
    assert response.status_code == 200
    assert response.json() == {"role": "OWNER"}


def test_without_a_session_it_is_401(owner_only_app: FastAPI, owner: tuple[TestClient, str]):
    _, patient_id = owner
    stranger = TestClient(owner_only_app, follow_redirects=False)
    assert stranger.get(f"/patients/{patient_id}/owner-thing").status_code == 401


def test_a_stranger_gets_404_and_the_attempt_is_recorded(
    owner: tuple[TestClient, str], second_person: tuple[TestClient, User], db: Session
):
    _, patient_id = owner
    stranger, stranger_user = second_person

    response = stranger.get(f"/patients/{patient_id}/owner-thing")

    assert response.status_code == 404
    (event,) = denied_events(db)
    assert (event.patient_id, event.user_id) == (patient_id, stranger_user.id)


def test_a_patient_that_does_not_exist_looks_the_same_as_one_you_cannot_see(
    owner: tuple[TestClient, str], db: Session
):
    client, _ = owner
    assert client.get(f"/patients/{new_id()}/owner-thing").status_code == 404
    assert len(denied_events(db)) == 1


def test_an_aide_is_refused_an_owner_only_route_with_403(
    owner: tuple[TestClient, str],
    second_person: tuple[TestClient, User],
    db: Session,
):
    _, patient_id = owner
    aide, aide_user = second_person
    grant(db, patient_id, aide_user, role=Role.AIDE)

    assert aide.get(f"/patients/{patient_id}/owner-thing").status_code == 403
    assert [e.user_id for e in denied_events(db)] == [aide_user.id]


def test_an_aide_can_use_a_route_that_allows_aides(
    owner: tuple[TestClient, str],
    second_person: tuple[TestClient, User],
    db: Session,
):
    _, patient_id = owner
    aide, aide_user = second_person
    grant(db, patient_id, aide_user, role=Role.AIDE)

    response = aide.get(f"/patients/{patient_id}/shared-thing")
    assert response.status_code == 200
    assert response.json() == {"role": "AIDE"}


@pytest.mark.parametrize("status", [AccessStatus.PENDING, AccessStatus.REVOKED])
def test_access_that_is_not_active_does_not_count(
    owner: tuple[TestClient, str],
    second_person: tuple[TestClient, User],
    db: Session,
    status: AccessStatus,
):
    _, patient_id = owner
    aide, aide_user = second_person
    grant(db, patient_id, aide_user, role=Role.AIDE, status=status)

    assert aide.get(f"/patients/{patient_id}/shared-thing").status_code == 404


def test_access_that_has_expired_does_not_count(
    owner: tuple[TestClient, str],
    second_person: tuple[TestClient, User],
    db: Session,
):
    _, patient_id = owner
    aide, aide_user = second_person
    grant(db, patient_id, aide_user, role=Role.AIDE, expires_at=utc_now() - timedelta(minutes=1))

    assert aide.get(f"/patients/{patient_id}/shared-thing").status_code == 404


def test_revoking_access_takes_effect_on_the_next_request(
    owner: tuple[TestClient, str],
    second_person: tuple[TestClient, User],
    db: Session,
):
    _, patient_id = owner
    aide, aide_user = second_person
    access = grant(db, patient_id, aide_user, role=Role.AIDE)
    assert aide.get(f"/patients/{patient_id}/shared-thing").status_code == 200

    access.status = AccessStatus.REVOKED
    db.add(access)
    db.commit()

    assert aide.get(f"/patients/{patient_id}/shared-thing").status_code == 404


def test_a_stranger_cannot_see_the_owners_patient_in_me(
    owner: tuple[TestClient, str],
    second_person: tuple[TestClient, User],
    db: Session,
):
    _, patient_id = owner
    stranger, _ = second_person
    ids = [p["id"] for p in stranger.get("/me").json()["patients"]]
    assert patient_id not in ids
    assert db.get(Patient, patient_id) is not None


@pytest.mark.parametrize("origin", [UI_URL, BACKEND_URL, f"{UI_URL}/"])
def test_a_change_from_our_own_sites_is_allowed(client: TestClient, origin: str):
    assert client.post("/auth/logout", headers={"origin": origin}).status_code == 303


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://localhost:9999"])
def test_a_change_from_any_other_site_is_refused(client: TestClient, origin: str):
    assert client.post("/auth/logout", headers={"origin": origin}).status_code == 403


def test_reading_from_another_site_is_not_blocked_by_the_origin_check(client: TestClient):
    response = client.get("/health", headers={"origin": "https://evil.example"})
    assert response.status_code == 200


def test_the_origin_check_covers_every_route_that_changes_data(
    app: FastAPI, client: TestClient, new_client: Callable[[], TestClient]
):
    @app.post("/anything")
    def anything() -> dict[str, bool]:
        return {"ok": True}

    assert client.post("/anything", headers={"origin": "https://evil.example"}).status_code == 403
    assert client.post("/anything").status_code == 200
