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
