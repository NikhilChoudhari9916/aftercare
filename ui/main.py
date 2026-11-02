import os
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import Request
from nicegui import app, ui

from ui.api_client import COOKIE_NAME, BackendClient, BackendUnavailable
from ui.content import describe_role, error_message, sign_in_url, sign_out_form
from ui.security import SecurityHeadersMiddleware

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ui/ never imports from app/, so it reads the few settings it needs itself.
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
UI_URL = os.environ.get("UI_URL", "http://localhost:8080")
UI_HOST = os.environ.get("UI_HOST", "127.0.0.1")
UI_PORT = urlsplit(UI_URL).port or 8080

backend = BackendClient(BACKEND_URL)
app.add_middleware(SecurityHeadersMiddleware)


def link_button(text: str, url: str, *, outline: bool = False) -> None:
    props = f'href="{escape(url, quote=True)}" size=lg no-caps unelevated'
    props += " outline color=primary" if outline else " color=primary"
    ui.button(text).props(props).classes("w-full min-h-12")


@ui.page("/")
async def home(request: Request, error: str | None = None) -> None:
    ui.colors(primary="#0f6e56")
    try:
        me = await backend.me(request.cookies.get(COOKIE_NAME))
    except BackendUnavailable:
        with page_column():
            heading("AfterCare")
            ui.label("AfterCare can't reach its server right now. Please try again in a moment.")
            link_button("Try again", "/")
            footer()
        return

    with page_column():
        if me is None:
            heading("AfterCare")
            ui.label(
                "Understand your hospital discharge papers: what each medicine is for, "
                "when to take it, and what to do while you recover."
            ).classes("text-lg")
            message = error_message(error)
            if message:
                ui.label(message).classes("text-negative text-base").props('role="alert"')
            link_button("Sign in with Google", sign_in_url(BACKEND_URL))
        else:
            heading(f"Hello, {me.user.display_name}")
            ui.label(describe_role(me)).classes("text-lg")
            ui.html(sign_out_form(BACKEND_URL), sanitize=False)
        footer()


def page_column() -> ui.column:
    return ui.column().classes("w-full max-w-md mx-auto px-4 py-8 gap-6 items-stretch")


def heading(text: str) -> None:
    ui.label(text).classes("text-3xl font-medium break-words")


def footer() -> None:
    ui.label("Synthetic data only. Not medical advice.").classes("text-sm text-grey-7")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host=UI_HOST,
        port=UI_PORT,
        title="AfterCare",
        reload=False,
        show=False,
        show_welcome_message=False,
    )
