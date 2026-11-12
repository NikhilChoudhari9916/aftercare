import os
from html import escape
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Request
from nicegui import ui

from ui.api_client import COOKIE_NAME, BackendClient, BackendUnavailable, Me, PatientRef

# ui/ never imports from app/, so it reads the few settings it needs itself. The .env file
# is loaded here, before anything reads the environment.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")

backend = BackendClient(BACKEND_URL)

PRIMARY_COLOR = "#0f6e56"


def setup_page() -> None:
    """Every page uses the same colors, and always the light theme: the text colors are chosen
    for a light background, so a phone set to dark mode must not turn the page dark."""
    ui.colors(primary=PRIMARY_COLOR)
    ui.dark_mode(False)
    # Without an explicit background the browser paints its own dark canvas behind the page.
    ui.add_css("html, body { background: #ffffff; color: #1a1a1a; color-scheme: light; }")


def page_column() -> ui.column:
    return ui.column().classes("w-full max-w-md mx-auto px-4 py-8 gap-6 items-stretch")


def heading(text: str) -> None:
    ui.label(text).classes("text-3xl font-medium break-words")


def footer() -> None:
    ui.label("Synthetic data only. Not medical advice.").classes("text-sm text-grey-7")


def link_button(text: str, url: str, *, outline: bool = False) -> None:
    props = f'href="{escape(url, quote=True)}" size=lg no-caps unelevated'
    props += " outline color=primary" if outline else " color=primary"
    ui.button(text).props(props).classes("w-full min-h-12")


def session_token(request: Request) -> str | None:
    return request.cookies.get(COOKIE_NAME)


def show_server_down() -> None:
    with page_column():
        heading("AfterCare")
        ui.label("AfterCare can't reach its server right now. Please try again in a moment.")
        link_button("Try again", "/")
        footer()


async def signed_in_owner(request: Request) -> tuple[Me, PatientRef] | None:
    """The signed-in patient for a page, or None after sending the browser somewhere sensible.

    The UI keeps no auth state: it asks the backend on every page (ADR-0033)."""
    setup_page()
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
        with page_column():
            heading("AfterCare")
            ui.label("Only the patient can upload and confirm their papers.")
            link_button("Back", "/", outline=True)
            footer()
        return None
    return me, owner
