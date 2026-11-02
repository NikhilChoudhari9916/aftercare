import asyncio

import httpx
import pytest

from app.auth.session import COOKIE_NAME as BACKEND_COOKIE_NAME
from ui.api_client import COOKIE_NAME, BackendClient, BackendUnavailable

TOKEN = "t" * 43
ME = {
    "user": {"id": "u1", "email": "ada@example.com", "display_name": "Ada Lovelace"},
    "patients": [{"id": "p1", "role": "OWNER"}],
}


def client_with(handler) -> BackendClient:
    return BackendClient("http://backend.test", transport=httpx.MockTransport(handler))


def ask(client: BackendClient, token):
    return asyncio.run(client.me(token))


def test_the_cookie_name_matches_the_backend():
    assert COOKIE_NAME == BACKEND_COOKIE_NAME


def test_a_signed_in_user_comes_back_and_the_cookie_is_forwarded():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["cookie"] = request.headers.get("cookie")
        return httpx.Response(200, json=ME)

    me = ask(client_with(handler), TOKEN)

    assert me.user.display_name == "Ada Lovelace"
    assert [(p.id, p.role) for p in me.patients] == [("p1", "OWNER")]
    assert seen["url"] == "http://backend.test/me"
    assert seen["cookie"] == f"{COOKIE_NAME}={TOKEN}"


def test_a_401_means_nobody_is_signed_in():
    assert ask(client_with(lambda request: httpx.Response(401)), TOKEN) is None


@pytest.mark.parametrize(
    "token", [None, "", "short", "has space " + "x" * 30, "bad;cookie" + "x" * 30]
)
def test_a_missing_or_odd_token_is_signed_out_without_calling_the_backend(token):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the backend should not be called")

    assert ask(client_with(handler), token) is None


def test_a_backend_that_is_down_is_reported_not_treated_as_signed_out():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(BackendUnavailable):
        ask(client_with(handler), TOKEN)


@pytest.mark.parametrize("status", [500, 503, 403, 404])
def test_an_unexpected_status_is_reported(status):
    with pytest.raises(BackendUnavailable):
        ask(client_with(lambda request: httpx.Response(status)), TOKEN)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json={"unexpected": "shape"}),
    ],
)
def test_an_unexpected_body_is_reported(response):
    with pytest.raises(BackendUnavailable):
        ask(client_with(lambda request: response), TOKEN)
