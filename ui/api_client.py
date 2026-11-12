import re
from typing import Any

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


class NotSignedIn(Exception):
    """No valid session: the page should send the person to sign in."""


class Rejected(Exception):
    """The backend refused the request. The message is already plain language."""


class UploadResult(BaseModel):
    job_id: str
    document_id: str


class JobInfo(BaseModel):
    status: str
    step: str | None
    error_code: str | None
    message: str | None


class DraftItem(BaseModel):
    id: str
    section: str
    data: dict[str, Any]
    quote_status: str
    confirmed: bool


class InjectionFlag(BaseModel):
    page: int
    kind: str


class Draft(BaseModel):
    version_id: str
    status: str
    discharge_date: str | None
    injection_flags: list[InjectionFlag]
    items: list[DraftItem]


GENERIC_REJECTION = "Something went wrong. Please try again."
UPLOAD_TIMEOUT_SECONDS = 60.0


class SummaryLine(BaseModel):
    text: str
    source_page: int | None = None


class SummarySection(BaseModel):
    key: str
    title: str
    lines: list[SummaryLine]


class Summary(BaseModel):
    version: int
    intro: str
    sections: list[SummarySection]


class MedicineLine(BaseModel):
    name: str
    other_names: list[str]
    dose: str | None
    how_often: str
    status: str
    end_date: str | None
    source_page: int
    item_id: str = ""
    times: list[str] = []
    suggested_times: list[str] = []
    times_needed: int | None = None
    chosen: bool = False


class DoseTime(BaseModel):
    slot: str
    label: str
    time: str
    medicines: list[MedicineLine]


class FollowUpLine(BaseModel):
    item_id: str = ""
    what: str
    when: str
    with_whom: str | None
    kind: str = "no_date"  # booked_time, date_only, window, or no_date (what the papers gave)
    papers_date: str | None = None
    papers_time: str | None = None
    status: str | None = None  # BOOKED or NOT_BOOKED once the patient has saved a plan
    date: str | None
    time: str | None
    call_on: str | None = None
    chosen: bool = False
    in_calendar: bool
    source_page: int


class Schedule(BaseModel):
    version: int
    daily: list[DoseTime]
    needs_timing: list[MedicineLine]
    plan_medicines: list[MedicineLine] = []
    as_needed: list[MedicineLine]
    stopped: list[MedicineLine]
    follow_ups: list[FollowUpLine]


def _rejection_message(response: httpx.Response) -> str:
    """The backend's own plain-language sentence, or a generic one. Never a status code."""
    try:
        detail = response.json().get("detail")
    except ValueError:
        return GENERIC_REJECTION
    if isinstance(detail, dict):
        detail = detail.get("message")
    return detail if isinstance(detail, str) else GENERIC_REJECTION


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

    async def _send(
        self,
        method: str,
        path: str,
        session_token: str | None,
        *,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        if not session_token or not TOKEN_PATTERN.match(session_token):
            raise NotSignedIn
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, transport=self._transport, timeout=timeout or self._timeout
            ) as http:
                response = await http.request(
                    method, path, headers={"Cookie": f"{COOKIE_NAME}={session_token}"}, **kwargs
                )
        except httpx.HTTPError as error:
            raise BackendUnavailable(type(error).__name__) from error
        if response.status_code == 401:
            raise NotSignedIn
        return response

    @staticmethod
    def _parse[T: BaseModel](model: type[T], response: httpx.Response) -> T:
        try:
            return model.model_validate(response.json())
        except ValueError as error:
            raise BackendUnavailable("unexpected response") from error

    async def upload_document(
        self, session_token: str | None, patient_id: str, filename: str, data: bytes
    ) -> UploadResult:
        response = await self._send(
            "POST",
            "/documents",
            session_token,
            timeout=UPLOAD_TIMEOUT_SECONDS,
            data={"patient_id": patient_id},
            files={"file": (filename, data, "application/pdf")},
        )
        if response.status_code in (404, 422, 503):
            raise Rejected(_rejection_message(response))
        if response.status_code != 202:
            raise BackendUnavailable(f"status {response.status_code}")
        return self._parse(UploadResult, response)

    async def get_job(self, session_token: str | None, job_id: str) -> JobInfo:
        response = await self._send("GET", f"/jobs/{job_id}", session_token)
        if response.status_code != 200:
            raise BackendUnavailable(f"status {response.status_code}")
        return self._parse(JobInfo, response)

    async def get_draft(self, session_token: str | None, patient_id: str) -> Draft | None:
        """The latest reading of the patient's papers, or None if nothing was uploaded yet."""
        response = await self._send("GET", f"/patients/{patient_id}/extraction", session_token)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise BackendUnavailable(f"status {response.status_code}")
        return self._parse(Draft, response)

    async def confirm_profile(
        self,
        session_token: str | None,
        patient_id: str,
        version_id: str,
        decisions: list[dict[str, Any]],
    ) -> Draft:
        response = await self._send(
            "PUT",
            f"/patients/{patient_id}/profile",
            session_token,
            json={"version_id": version_id, "items": decisions},
        )
        if response.status_code in (404, 409, 422):
            raise Rejected(_rejection_message(response))
        if response.status_code != 200:
            raise BackendUnavailable(f"status {response.status_code}")
        return self._parse(Draft, response)

    async def _get_confirmed[T: BaseModel](
        self, model: type[T], session_token: str | None, path: str
    ) -> T | None:
        """A page built from the confirmed profile, or None while nothing is confirmed yet."""
        response = await self._send("GET", path, session_token)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise BackendUnavailable(f"status {response.status_code}")
        return self._parse(model, response)

    async def get_summary(self, session_token: str | None, patient_id: str) -> Summary | None:
        return await self._get_confirmed(Summary, session_token, f"/patients/{patient_id}/summary")

    async def get_schedule(self, session_token: str | None, patient_id: str) -> Schedule | None:
        return await self._get_confirmed(
            Schedule, session_token, f"/patients/{patient_id}/schedule"
        )

    async def save_plan(
        self, session_token: str | None, patient_id: str, plan: dict[str, Any]
    ) -> Schedule:
        """Save the patient's reminder times and visit plans, all at once (ADR-0042)."""
        response = await self._send("PUT", f"/patients/{patient_id}/plan", session_token, json=plan)
        if response.status_code in (403, 404, 422):
            raise Rejected(_rejection_message(response))
        if response.status_code != 200:
            raise BackendUnavailable(f"status {response.status_code}")
        return self._parse(Schedule, response)
