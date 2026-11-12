from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.session import COOKIE_NAME
from app.config import Settings
from app.models import LoginSession, Patient, PatientAccess, Role, User
from tests.auth.helpers import UI_URL, FakeProvider, count, make_settings, sign_in


@pytest.fixture
def dev_app(make_app: Callable[[Settings], FastAPI], tmp_path) -> FastAPI:
    return make_app(make_settings(dev_login=True, storage_dir=tmp_path))


def browser(app: FastAPI, host: str = "localhost") -> TestClient:
    return TestClient(app, base_url=f"http://{host}:8000", follow_redirects=False)


def test_the_test_login_signs_in_a_fixed_synthetic_patient(dev_app: FastAPI, db: Session):
    client = browser(dev_app)

    response = client.post("/auth/dev-login", data={"persona": "alex"})

    assert response.status_code == 303
    assert response.headers["location"] == f"{UI_URL}/"
    assert COOKIE_NAME in client.cookies
    me = client.get("/me").json()
    assert me["user"]["email"] == "alex@aftercare.test"
    assert [patient["role"] for patient in me["patients"]] == ["OWNER"]
    assert count(db, User) == 1
    assert count(db, Patient) == 1


def test_signing_in_again_reuses_the_person_and_replaces_the_session(dev_app: FastAPI, db: Session):
    client = browser(dev_app)
    client.post("/auth/dev-login", data={"persona": "alex"})
    first_token = client.cookies[COOKIE_NAME]

    client.post("/auth/dev-login", data={"persona": "alex"})

    assert client.cookies[COOKIE_NAME] != first_token
    assert (count(db, User), count(db, Patient), count(db, LoginSession)) == (1, 1, 1)


def test_the_two_test_people_cannot_see_each_others_patient(dev_app: FastAPI, db: Session):
    alex, sam = browser(dev_app), browser(dev_app)
    alex.post("/auth/dev-login", data={"persona": "alex"})
    sam.post("/auth/dev-login", data={"persona": "sam"})
    alex_patient = alex.get("/me").json()["patients"][0]["id"]

    # Alex passes the access check and reaches "no document yet"; Sam is stopped before that.
    assert alex.get(f"/patients/{alex_patient}/extraction").json()["detail"] == (
        "No document has been read yet"
    )
    assert sam.get(f"/patients/{alex_patient}/extraction").json()["detail"] == "Not found"
    assert count(db, PatientAccess) == 2
    assert {access.role for access in db.exec(select(PatientAccess)).all()} == {Role.OWNER}


def test_it_does_not_exist_unless_it_was_switched_on(
    make_app: Callable[[Settings], FastAPI], db: Session, tmp_path
):
    client = browser(make_app(make_settings(storage_dir=tmp_path)))

    response = client.post("/auth/dev-login", data={"persona": "alex"})

    assert response.status_code == 404
    assert COOKIE_NAME not in client.cookies
    assert count(db, User) == 0


def test_it_is_refused_when_the_request_does_not_come_from_a_local_address(
    dev_app: FastAPI, db: Session
):
    client = browser(dev_app, host="demo.example.com")

    response = client.post("/auth/dev-login", data={"persona": "alex"})

    assert response.status_code == 404
    assert count(db, User) == 0


def test_an_unknown_person_is_refused(dev_app: FastAPI, db: Session):
    response = browser(dev_app).post("/auth/dev-login", data={"persona": "root"})
    assert response.status_code == 422
    assert count(db, User) == 0


def test_a_form_posted_from_another_site_is_refused(dev_app: FastAPI, db: Session):
    response = browser(dev_app).post(
        "/auth/dev-login", data={"persona": "alex"}, headers={"origin": "https://evil.example"}
    )
    assert response.status_code == 403
    assert count(db, User) == 0


def test_the_ui_origin_may_post_the_form(dev_app: FastAPI):
    response = browser(dev_app).post(
        "/auth/dev-login", data={"persona": "alex"}, headers={"origin": UI_URL}
    )
    assert response.status_code == 303


def test_a_test_login_person_never_collides_with_a_google_account(
    dev_app: FastAPI, provider: FakeProvider, db: Session
):
    browser(dev_app).post("/auth/dev-login", data={"persona": "alex"})
    google = browser(dev_app)
    sign_in(google, provider, sub="123456789", email="alex@aftercare.test", name="Someone Else")

    assert count(db, User) == 2


def test_google_sign_in_still_works_with_the_test_login_on(
    dev_app: FastAPI, provider: FakeProvider
):
    client = browser(dev_app)

    response = sign_in(client, provider)

    assert response.status_code == 303
    assert client.get("/me").json()["user"]["email"] == "ada@example.com"


@pytest.mark.parametrize(
    "overrides",
    [
        {"app_env": "production"},
        {"backend_url": "https://aftercare.example.com"},
        {"backend_url": "http://192.168.1.20:8000"},
    ],
)
def test_the_app_refuses_to_be_configured_with_the_test_login_outside_local_development(
    overrides,
):
    with pytest.raises(ValueError, match="DEV_LOGIN"):
        make_settings(dev_login=True, **overrides)


@pytest.mark.parametrize(
    "backend", ["http://localhost:8000", "http://127.0.0.1:8000", "http://[::1]:8000"]
)
def test_local_addresses_are_allowed(backend: str):
    assert make_settings(dev_login=True, backend_url=backend).dev_login is True


def test_it_is_off_by_default_and_can_be_switched_on_from_the_environment(monkeypatch):
    assert make_settings().dev_login is False
    monkeypatch.setenv("DEV_LOGIN", "1")
    assert Settings.from_env().dev_login is True
