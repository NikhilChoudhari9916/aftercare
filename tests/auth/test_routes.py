import asyncio
from collections.abc import Callable
from urllib.parse import parse_qs, urlparse

import pytest
from authlib.integrations.base_client.errors import MismatchingStateError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.google import GoogleProvider, LoginFailed, get_identity_provider
from app.config import Settings
from app.models import (
    AccessEvent,
    AccessEventKind,
    LoginSession,
    Patient,
    PatientAccess,
    Role,
    User,
)
from tests.auth.helpers import (
    UI_URL,
    FakeProvider,
    count,
    make_settings,
    session_cookie,
    sign_in,
)


def test_me_without_a_session_is_401(client: TestClient):
    assert client.get("/me").status_code == 401


def test_first_sign_in_creates_user_patient_owner_access_and_a_session(
    client: TestClient, provider: FakeProvider, db: Session
):
    response = sign_in(client, provider)

    assert response.status_code == 303
    assert response.headers["location"] == f"{UI_URL}/"
    cookie = session_cookie(response).lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "secure" not in cookie

    me = client.get("/me")
    assert me.status_code == 200
    assert me.headers["cache-control"] == "no-store"
    body = me.json()
    assert body["user"]["email"] == "ada@example.com"
    assert body["user"]["display_name"] == "Ada Lovelace"
    assert [p["role"] for p in body["patients"]] == ["OWNER"]

    assert count(db, User) == 1
    assert count(db, Patient) == 1
    assert count(db, LoginSession) == 1
    access = db.exec(select(PatientAccess)).one()
    assert access.role == Role.OWNER
    assert access.patient_id == body["patients"][0]["id"]
    event = db.exec(select(AccessEvent)).one()
    assert event.kind == AccessEventKind.PATIENT_CREATED


def test_signing_in_again_makes_no_duplicates_and_replaces_the_old_session(
    client: TestClient, provider: FakeProvider, db: Session
):
    sign_in(client, provider)
    sign_in(client, provider)

    assert count(db, User) == 1
    assert count(db, Patient) == 1
    assert count(db, PatientAccess) == 1
    assert count(db, LoginSession) == 1
    assert client.get("/me").status_code == 200


def test_a_changed_name_and_email_are_updated_on_the_next_sign_in(
    client: TestClient, provider: FakeProvider, db: Session
):
    sign_in(client, provider)
    sign_in(client, provider, email="ada@new.example", name="Ada King")

    user = db.exec(select(User)).one()
    assert (user.email, user.display_name) == ("ada@new.example", "Ada King")


def test_two_people_get_separate_patients(
    client: TestClient,
    new_client: Callable[[], TestClient],
    provider: FakeProvider,
    db: Session,
):
    other = new_client()
    sign_in(client, provider, sub="sub-a", email="a@example.com")
    sign_in(other, provider, sub="sub-b", email="b@example.com")

    mine = client.get("/me").json()["patients"][0]["id"]
    theirs = other.get("/me").json()["patients"][0]["id"]
    assert mine != theirs
    assert count(db, Patient) == 2


@pytest.mark.parametrize("verified", [False, None, "true"])
def test_an_email_google_has_not_verified_is_rejected(
    client: TestClient, provider: FakeProvider, db: Session, verified
):
    response = sign_in(client, provider, verified=verified)

    assert response.status_code == 303
    assert response.headers["location"] == f"{UI_URL}/?error=email_not_verified"
    assert session_cookie(response) is None
    assert count(db, User) == 0


def test_a_claim_set_without_a_subject_or_email_is_rejected(
    client: TestClient, provider: FakeProvider, db: Session
):
    provider.claims = {"email": "ada@example.com", "email_verified": True}
    response = client.get("/auth/callback")
    assert response.headers["location"] == f"{UI_URL}/?error=email_not_verified"
    assert count(db, User) == 0


def test_a_failed_login_goes_back_to_the_ui_with_an_error_and_no_session(
    client: TestClient, provider: FakeProvider, db: Session
):
    provider.fail = True
    response = client.get("/auth/callback")

    assert response.status_code == 303
    assert response.headers["location"] == f"{UI_URL}/?error=sign_in_failed"
    assert session_cookie(response) is None
    assert count(db, LoginSession) == 0


def test_login_sends_the_browser_to_the_provider(client: TestClient):
    response = client.get("/auth/login")
    assert response.status_code == 303
    assert response.headers["location"] == "https://accounts.example/authorize"


def test_login_says_so_when_google_sign_in_is_not_configured(
    make_app: Callable[[Settings], FastAPI],
):
    client = TestClient(make_app(make_settings(google_client_id="")), follow_redirects=False)
    assert client.get("/auth/login").status_code == 503


def test_a_safe_next_path_is_kept(client: TestClient, provider: FakeProvider):
    client.get("/auth/login", params={"next": "/summary"})
    response = sign_in(client, provider)
    assert response.headers["location"] == f"{UI_URL}/summary"


@pytest.mark.parametrize(
    "unsafe",
    ["//evil.example", "https://evil.example", "/\\evil.example", "@evil.example", "/a\nb", ""],
)
def test_an_unsafe_next_path_falls_back_to_the_home_page(
    client: TestClient, provider: FakeProvider, unsafe: str
):
    client.get("/auth/login", params={"next": unsafe})
    response = sign_in(client, provider)
    assert response.headers["location"] == f"{UI_URL}/"


def test_logout_ends_the_session_for_good_and_clears_the_cookie(
    client: TestClient, provider: FakeProvider, db: Session
):
    sign_in(client, provider)
    old_token = client.cookies.get("aftercare_session")

    response = client.post("/auth/logout", headers={"origin": UI_URL})

    assert response.status_code == 303
    assert response.headers["location"] == UI_URL
    assert "max-age=0" in session_cookie(response).lower()
    assert count(db, LoginSession) == 0

    client.cookies.clear()
    client.cookies.set("aftercare_session", old_token)
    assert client.get("/me").status_code == 401


def test_logout_without_a_session_is_harmless(client: TestClient):
    assert client.post("/auth/logout").status_code == 303


def test_logout_from_an_unexpected_site_is_refused_and_keeps_the_session(
    client: TestClient, provider: FakeProvider, db: Session
):
    sign_in(client, provider)
    response = client.post("/auth/logout", headers={"origin": "https://evil.example"})

    assert response.status_code == 403
    assert count(db, LoginSession) == 1
    assert client.get("/me").status_code == 200


def test_the_cookie_is_secure_in_production(
    make_app: Callable[[Settings], FastAPI], provider: FakeProvider
):
    app = make_app(make_settings(app_env="production"))
    response = sign_in(TestClient(app, follow_redirects=False), provider)
    assert "secure" in session_cookie(response).lower()


def test_google_errors_become_a_failed_login(monkeypatch: pytest.MonkeyPatch):
    google = GoogleProvider(make_settings())

    async def bad_state(_request):
        raise MismatchingStateError()

    monkeypatch.setattr(google._client, "authorize_access_token", bad_state)
    with pytest.raises(LoginFailed):
        asyncio.run(google.finish_login(request=None))


def test_a_google_reply_without_identity_claims_is_a_failed_login(
    monkeypatch: pytest.MonkeyPatch,
):
    google = GoogleProvider(make_settings())

    async def no_claims(_request):
        return {"access_token": "x"}

    monkeypatch.setattr(google._client, "authorize_access_token", no_claims)
    with pytest.raises(LoginFailed):
        asyncio.run(google.finish_login(request=None))


GOOGLE_METADATA = {
    "issuer": "https://accounts.google.com",
    "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
}


@pytest.fixture
def real_google_app(make_app: Callable[[Settings], FastAPI]) -> FastAPI:
    """The app wired to the real Authlib code, with Google's endpoints supplied locally."""

    google = GoogleProvider(make_settings())

    async def local_metadata():
        return GOOGLE_METADATA

    google._client.load_server_metadata = local_metadata
    app = make_app(make_settings())
    app.dependency_overrides[get_identity_provider] = lambda: google
    return app


def test_the_real_login_redirect_carries_state_nonce_and_a_pkce_challenge(
    real_google_app: FastAPI,
):
    client = TestClient(real_google_app, follow_redirects=False)
    response = client.get("/auth/login")

    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    assert (
        f"{location.scheme}://{location.netloc}{location.path}"
        == (GOOGLE_METADATA["authorization_endpoint"])
    )
    query = parse_qs(location.query)
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["openid email profile"]
    assert query["redirect_uri"] == ["http://localhost:8000/auth/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["code_challenge"][0]) >= 43
    assert len(query["state"][0]) >= 20
    assert len(query["nonce"][0]) >= 20


def test_a_forged_state_on_the_real_callback_is_a_failed_login(
    real_google_app: FastAPI, db: Session
):
    client = TestClient(real_google_app, follow_redirects=False)
    client.get("/auth/login")
    response = client.get("/auth/callback", params={"code": "anything", "state": "forged"})

    assert response.status_code == 303
    assert response.headers["location"] == f"{UI_URL}/?error=sign_in_failed"
    assert session_cookie(response) is None
    assert count(db, User) == 0


def test_a_callback_with_no_login_in_progress_is_a_failed_login(real_google_app: FastAPI):
    client = TestClient(real_google_app, follow_redirects=False)
    response = client.get("/auth/callback", params={"code": "anything", "state": "anything"})
    assert response.headers["location"] == f"{UI_URL}/?error=sign_in_failed"


def test_the_cookie_is_secure_when_the_backend_uses_https_even_outside_production(
    make_app: Callable[[Settings], FastAPI], provider: FakeProvider
):
    app = make_app(make_settings(backend_url="https://api.example.com"))
    response = sign_in(TestClient(app, follow_redirects=False), provider)
    assert "secure" in session_cookie(response).lower()


def test_a_very_long_display_name_is_cut_down(
    client: TestClient, provider: FakeProvider, db: Session
):
    sign_in(client, provider, name="N" * 500)
    assert len(db.exec(select(User)).one().display_name) == 200
