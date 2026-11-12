from html import escape

from ui.api_client import Me

GENERIC_SIGN_IN_ERROR = "Something went wrong signing you in. Please try again."

SIGN_IN_ERRORS = {
    "sign_in_failed": "We couldn't sign you in with Google. Please try again.",
    "email_not_verified": (
        "Google says your email address isn't verified. "
        "Please verify it with Google, then try again."
    ),
}


def error_message(code: str | None) -> str | None:
    """Turn the backend's error code into a friendly sentence. Never repeats the code itself."""
    if not code:
        return None
    return SIGN_IN_ERRORS.get(code, GENERIC_SIGN_IN_ERROR)


def describe_role(me: Me) -> str:
    roles = {patient.role for patient in me.patients}
    if "OWNER" in roles:
        return "You are signed in as the patient."
    if "AIDE" in roles:
        return "You are signed in as an aide."
    return "You are signed in."


def sign_in_url(backend_url: str) -> str:
    return f"{backend_url}/auth/login?next=/"


def dev_sign_in_form(backend_url: str, persona: str, label: str) -> str:
    """The development-only test login button (ADR-0037). The backend refuses it anywhere but
    a developer's own machine, so showing it is never what protects anything."""
    action = escape(f"{backend_url}/auth/dev-login", quote=True)
    return (
        f'<form method="post" action="{action}" style="width:100%">'
        f'<input type="hidden" name="persona" value="{escape(persona, quote=True)}">'
        '<button type="submit" '
        'style="width:100%;min-height:48px;font-size:1rem;border:1px dashed #888;'
        'border-radius:4px;background:transparent;color:inherit;cursor:pointer">'
        f"{escape(label)}</button></form>"
    )


def sign_out_form(backend_url: str) -> str:
    """A plain form, so the browser itself posts to the backend and receives the cookie-clearing
    response (ADR-0033). Built only from our own configuration, never from user data."""
    action = escape(f"{backend_url}/auth/logout", quote=True)
    return (
        f'<form method="post" action="{action}" style="width:100%">'
        '<button type="submit" '
        'style="width:100%;min-height:48px;font-size:1rem;border:1px solid #888;'
        'border-radius:4px;background:transparent;color:inherit;cursor:pointer">'
        "Sign out</button></form>"
    )
