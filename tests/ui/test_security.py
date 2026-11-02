import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient

from ui.security import SECURITY_HEADERS, SecurityHeadersMiddleware


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/page")
    def page() -> HTMLResponse:
        return HTMLResponse("<p>hello</p>")

    @app.get("/data")
    def data() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.get("/static.js")
    def static() -> PlainTextResponse:
        return PlainTextResponse(
            "x", media_type="text/javascript", headers={"Cache-Control": "public, max-age=31536000"}
        )

    return TestClient(app)


@pytest.mark.parametrize("path", ["/page", "/data", "/static.js"])
def test_every_response_gets_the_security_headers(client: TestClient, path: str):
    response = client.get(path)
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value


def test_the_page_cannot_be_framed():
    assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in SECURITY_HEADERS["Content-Security-Policy"]


def test_html_pages_are_never_cached(client: TestClient):
    assert client.get("/page").headers["cache-control"] == "no-store"


def test_static_files_keep_their_cache_lifetime(client: TestClient):
    assert client.get("/static.js").headers["cache-control"] == "public, max-age=31536000"


def test_the_referrer_policy_keeps_the_origin_header_intact_for_the_sign_out_form():
    # "same-origin" and "no-referrer" make browsers send "Origin: null" on a cross-origin
    # form post, which the backend refuses. Found in a real browser, so pinned here.
    assert SECURITY_HEADERS["Referrer-Policy"] == "strict-origin-when-cross-origin"
