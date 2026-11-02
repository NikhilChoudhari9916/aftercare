import re

import httpx
from pydantic import BaseModel

# Must match app/auth/session.py (a test checks it). ui/ never imports from app/.
COOKIE_NAME = "aftercare_session"

# What a real session token looks like; anything else is treated as "not signed in".
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,128}$")


class BackendUnavailable(Exception):
    """The backend did not answer, or answered with something unexpected."""


class UserInfo(BaseModel):
    id: str
    email: str
    display_name: str


class PatientRef(BaseModel):
    id: str
    role: str


class Me(BaseModel):
    user: UserInfo
    patients: list[PatientRef]


class BackendClient:
    """The only place in ui/ that talks to the backend (ADR-0003, ADR-0033)."""

    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._base_url = base_url
        self._transport = transport
        self._timeout = timeout

    async def me(self, session_token: str | None) -> Me | None:
        """Who is signed in? None means nobody. The UI keeps no auth state of its own."""
        if not session_token or not TOKEN_PATTERN.match(session_token):
            return None
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, transport=self._transport, timeout=self._timeout
            ) as http:
                response = await http.get(
                    "/me", headers={"Cookie": f"{COOKIE_NAME}={session_token}"}
                )
        except httpx.HTTPError as error:
            raise BackendUnavailable(type(error).__name__) from error

        if response.status_code == 401:
            return None
        if response.status_code != 200:
            raise BackendUnavailable(f"status {response.status_code}")
        try:
            return Me.model_validate(response.json())
        except ValueError as error:  # bad JSON or an unexpected shape
            raise BackendUnavailable("unexpected response") from error
