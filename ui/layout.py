from fastapi import Request
from nicegui import ui

from ui.api_client import BackendUnavailable, Me, PatientRef
from ui.backend import backend, session_token
from ui.components.basics import button
from ui.components.shell import app_shell
from ui.theme import apply_theme


def show_server_down() -> None:
    with app_shell():
        with ui.column().classes("ac-card ac-hero"):
            ui.label("We can't reach AfterCare's server").classes("ac-h2")
            ui.label("Please try again in a moment.").classes("ac-lead")
            button("Try again", href="/")


async def signed_in_owner(request: Request) -> tuple[Me, PatientRef] | None:
    """The signed-in patient for a page, or None after sending the browser somewhere sensible.

    The UI keeps no auth state: it asks the backend on every page (ADR-0033)."""
    apply_theme()
    try:
        me = await backend.me(session_token(request))
    except BackendUnavailable:
        show_server_down()
        return None
    if me is None:
        ui.navigate.to("/")
        return None
    owner = next((patient for patient in me.patients if patient.role == "OWNER"), None)
    if owner is None:
        with app_shell(me):
            with ui.column().classes("ac-card ac-hero"):
                ui.label("Only the patient can do this").classes("ac-h2")
                ui.label("Uploading and confirming papers is for the patient.").classes("ac-lead")
                button("Back to home", kind="ghost", href="/")
        return None
    return me, owner


async def signed_in_member(request: Request) -> tuple[Me, PatientRef] | None:
    """Like signed_in_owner, but an aide is welcome too: they may read the summary and schedule."""
    apply_theme()
    try:
        me = await backend.me(session_token(request))
    except BackendUnavailable:
        show_server_down()
        return None
    if me is None or not me.patients:
        ui.navigate.to("/")
        return None
    patient = next((p for p in me.patients if p.role == "OWNER"), me.patients[0])
    return me, patient


def show_not_confirmed(me: Me, patient: PatientRef, active: str) -> None:
    """Shown instead of the summary or schedule while nothing has been confirmed."""
    with app_shell(me, active=active):
        with ui.column().classes("ac-card ac-hero"):
            ui.label("Your papers aren't confirmed yet").classes("ac-h2")
            if patient.role == "OWNER":
                ui.label("Check each item AfterCare found, and this page will fill in.").classes(
                    "ac-lead"
                )
                button("Check what we found", href="/confirm")
            else:
                ui.label("The patient needs to confirm their papers first.").classes("ac-lead")
                button("Back to home", kind="ghost", href="/")
