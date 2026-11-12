import pytest

from ui.api_client import Me, PatientRef, UserInfo
from ui.content import (
    GENERIC_SIGN_IN_ERROR,
    describe_role,
    error_message,
    sign_in_url,
    sign_out_form,
)


def me_with(*roles: str) -> Me:
    return Me(
        user=UserInfo(id="u", email="a@example.com", display_name="Ada"),
        patients=[PatientRef(id=f"p{i}", role=role) for i, role in enumerate(roles)],
    )


def test_known_error_codes_get_a_friendly_sentence():
    assert "couldn't sign you in" in error_message("sign_in_failed")
    assert "isn't verified" in error_message("email_not_verified")


@pytest.mark.parametrize("code", [None, ""])
def test_no_error_means_no_message(code):
    assert error_message(code) is None


def test_an_unknown_code_gets_the_generic_message_and_is_never_repeated():
    message = error_message("<script>alert(1)</script>")
    assert message == GENERIC_SIGN_IN_ERROR
    assert "script" not in message


@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        (("OWNER",), "You are signed in as the patient."),
        (("AIDE",), "You are signed in as an aide."),
        (("OWNER", "AIDE"), "You are signed in as the patient."),
        ((), "You are signed in."),
    ],
)
def test_the_role_is_described_in_plain_words(roles, expected):
    assert describe_role(me_with(*roles)) == expected


def test_sign_in_goes_to_the_backend_and_returns_to_the_home_page():
    assert sign_in_url("http://localhost:8000") == "http://localhost:8000/auth/login?next=/"


def test_the_sign_out_form_posts_to_the_backend():
    html = sign_out_form("http://localhost:8000")
    assert 'method="post"' in html
    assert 'action="http://localhost:8000/auth/logout"' in html
    assert "min-height:48px" in html


def test_the_sign_out_form_escapes_the_address():
    html = sign_out_form('http://x.test/"><script>alert(1)</script>')
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
