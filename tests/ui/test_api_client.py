import asyncio

import httpx
import pytest

from app.auth.session import COOKIE_NAME as BACKEND_COOKIE_NAME
from ui.api_client import (
    COOKIE_NAME,
    BackendClient,
    BackendUnavailable,
    NotSignedIn,
    Rejected,
)

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


DRAFT = {
    "version_id": "v1",
    "version": 1,
    "status": "DRAFT",
    "discharge_date": "2026-10-12",
    "injection_flags": [{"page": 2, "kind": "ignore_rules", "excerpt": "ignore rules"}],
    "items": [
        {
            "id": "i1",
            "section": "medicines",
            "position": 0,
            "data": {"name_as_written": "furosemide", "source_page": 1},
            "quote_status": "verified",
            "confirmed": False,
        }
    ],
}


def run(coro):
    return asyncio.run(coro)


def test_an_upload_sends_the_file_and_patient_with_the_cookie_and_returns_the_job():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["cookie"] = request.headers.get("cookie")
        seen["body"] = request.content
        seen["path"] = request.url.path
        return httpx.Response(202, json={"job_id": "j1", "document_id": "d1"})

    result = run(
        client_with(handler).upload_document(TOKEN, "patient-1", "papers.pdf", b"%PDF-data")
    )

    assert (result.job_id, result.document_id) == ("j1", "d1")
    assert seen["path"] == "/documents"
    assert seen["cookie"] == f"{COOKIE_NAME}={TOKEN}"
    assert b"patient-1" in seen["body"] and b"%PDF-data" in seen["body"]


@pytest.mark.parametrize(
    ("status", "body", "message"),
    [
        (
            422,
            {"detail": {"code": "not_a_pdf", "message": "That file isn't a PDF."}},
            "That file isn't a PDF.",
        ),
        (503, {"detail": "AI service is not set up."}, "AI service is not set up."),
        (404, {"detail": "Not found"}, "Not found"),
        (422, {"detail": [{"loc": ["x"]}]}, "Something went wrong. Please try again."),
    ],
)
def test_a_refused_upload_becomes_a_plain_sentence(status, body, message):
    client = client_with(lambda request: httpx.Response(status, json=body))
    with pytest.raises(Rejected) as error:
        run(client.upload_document(TOKEN, "p1", "a.pdf", b"x"))
    assert str(error.value) == message


def test_a_refusal_that_is_not_json_still_gets_a_plain_sentence():
    client = client_with(lambda request: httpx.Response(422, text="oops"))
    with pytest.raises(Rejected, match="Something went wrong"):
        run(client.upload_document(TOKEN, "p1", "a.pdf", b"x"))


def test_a_missing_or_malformed_token_means_not_signed_in_without_calling_the_backend():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the backend must not be called")

    client = client_with(handler)
    for token in (None, "", "short"):
        with pytest.raises(NotSignedIn):
            run(client.get_job(token, "j1"))


@pytest.mark.parametrize("call", ["job", "draft", "upload", "confirm"])
def test_a_401_from_the_backend_means_not_signed_in(call):
    client = client_with(lambda request: httpx.Response(401, json={"detail": "Not signed in"}))
    calls = {
        "job": lambda: client.get_job(TOKEN, "j1"),
        "draft": lambda: client.get_draft(TOKEN, "p1"),
        "upload": lambda: client.upload_document(TOKEN, "p1", "a.pdf", b"x"),
        "confirm": lambda: client.confirm_profile(TOKEN, "p1", "v1", []),
    }
    with pytest.raises(NotSignedIn):
        run(calls[call]())


def test_job_progress_is_read():
    body = {"status": "RUNNING", "step": "extract", "error_code": None, "message": None}
    client = client_with(lambda request: httpx.Response(200, json=body))
    job = run(client.get_job(TOKEN, "j1"))
    assert (job.status, job.step) == ("RUNNING", "extract")


def test_the_draft_is_read_and_no_document_yet_is_none():
    ok = client_with(lambda request: httpx.Response(200, json=DRAFT))
    draft = run(ok.get_draft(TOKEN, "p1"))
    assert draft.version_id == "v1"
    assert [flag.page for flag in draft.injection_flags] == [2]
    assert draft.items[0].data["name_as_written"] == "furosemide"

    none_yet = client_with(lambda request: httpx.Response(404, json={"detail": "none"}))
    assert run(none_yet.get_draft(TOKEN, "p1")) is None


def test_confirming_sends_the_decisions_and_reads_the_result():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"], seen["path"] = request.method, request.url.path
        seen["json"] = request.read()
        return httpx.Response(200, json={**DRAFT, "status": "CONFIRMED"})

    decisions = [{"id": "i1", "action": "confirm"}]
    done = run(client_with(handler).confirm_profile(TOKEN, "p1", "v1", decisions))

    assert done.status == "CONFIRMED"
    assert (seen["method"], seen["path"]) == ("PUT", "/patients/p1/profile")
    assert b'"version_id":"v1"' in seen["json"].replace(b" ", b"")


@pytest.mark.parametrize("status", [404, 409, 422])
def test_a_refused_confirmation_becomes_a_plain_sentence(status):
    client = client_with(lambda request: httpx.Response(status, json={"detail": "Already done."}))
    with pytest.raises(Rejected, match="Already done."):
        run(client.confirm_profile(TOKEN, "p1", "v1", []))


def test_a_down_or_confusing_backend_is_unavailable_not_a_crash():
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with pytest.raises(BackendUnavailable):
        run(client_with(down).get_job(TOKEN, "j1"))
    with pytest.raises(BackendUnavailable):
        run(client_with(lambda r: httpx.Response(500)).get_draft(TOKEN, "p1"))
    with pytest.raises(BackendUnavailable):
        run(client_with(lambda r: httpx.Response(200, json={"nope": 1})).get_job(TOKEN, "j1"))
    with pytest.raises(BackendUnavailable):
        run(client_with(lambda r: httpx.Response(500)).upload_document(TOKEN, "p1", "a.pdf", b"x"))


SUMMARY = {
    "version": 1,
    "intro": "This is what your papers say.",
    "sections": [
        {
            "key": "medicines",
            "title": "Your medicines",
            "lines": [{"text": "Your papers list lisinopril.", "source_page": 1}],
        }
    ],
}
SCHEDULE = {
    "version": 1,
    "daily": [
        {
            "slot": "MORNING",
            "label": "Morning",
            "time": "08:00",
            "medicines": [
                {
                    "name": "lisinopril",
                    "other_names": [],
                    "dose": "10 mg",
                    "how_often": "once daily in the morning",
                    "status": "CONTINUED",
                    "end_date": None,
                    "source_page": 1,
                }
            ],
        }
    ],
    "needs_timing": [],
    "as_needed": [],
    "stopped": [],
    "follow_ups": [],
}


def test_the_summary_and_schedule_are_read_from_the_confirmed_profile():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        body = SUMMARY if request.url.path.endswith("/summary") else SCHEDULE
        return httpx.Response(200, json=body)

    client = client_with(handler)
    summary = asyncio.run(client.get_summary(TOKEN, "p1"))
    schedule = asyncio.run(client.get_schedule(TOKEN, "p1"))

    assert summary.sections[0].lines[0].source_page == 1
    assert schedule.daily[0].medicines[0].name == "lisinopril"
    assert seen == ["/patients/p1/summary", "/patients/p1/schedule"]


def test_nothing_confirmed_yet_is_none_not_an_error():
    client = client_with(lambda request: httpx.Response(404, json={"detail": "Not confirmed"}))
    assert asyncio.run(client.get_summary(TOKEN, "p1")) is None
    assert asyncio.run(client.get_schedule(TOKEN, "p1")) is None


def test_a_missing_session_or_a_down_backend_is_handled_for_the_new_pages():
    with pytest.raises(NotSignedIn):
        asyncio.run(client_with(lambda r: httpx.Response(200)).get_summary(None, "p1"))
    with pytest.raises(NotSignedIn):
        asyncio.run(client_with(lambda r: httpx.Response(401)).get_schedule(TOKEN, "p1"))
    with pytest.raises(BackendUnavailable):
        asyncio.run(client_with(lambda r: httpx.Response(500)).get_schedule(TOKEN, "p1"))
    with pytest.raises(BackendUnavailable):
        asyncio.run(
            client_with(lambda r: httpx.Response(200, json={"x": 1})).get_summary(TOKEN, "p1")
        )
