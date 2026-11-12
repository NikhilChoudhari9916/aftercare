import os
from urllib.parse import urlsplit

from fastapi import Request
from nicegui import app, ui

from ui.api_client import BackendUnavailable
from ui.content import (
    describe_role,
    dev_sign_in_form,
    error_message,
    sign_in_url,
    sign_out_form,
)
from ui.layout import (
    BACKEND_URL,
    backend,
    footer,
    heading,
    link_button,
    page_column,
    session_token,
    setup_page,
    show_server_down,
)
from ui.pages import confirm, upload  # noqa: F401  (importing registers the pages)
from ui.security import SecurityHeadersMiddleware

# ui/ never imports from app/, so it reads the few settings it needs itself.
UI_URL = os.environ.get("UI_URL", "http://localhost:8080")
UI_HOST = os.environ.get("UI_HOST", "127.0.0.1")
UI_PORT = urlsplit(UI_URL).port or 8080
DEV_LOGIN = os.environ.get("DEV_LOGIN", "").lower() in {"1", "true", "yes"}

app.add_middleware(SecurityHeadersMiddleware)


@ui.page("/")
async def home(request: Request, error: str | None = None) -> None:
    setup_page()
    try:
        me = await backend.me(session_token(request))
    except BackendUnavailable:
        show_server_down()
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
            if DEV_LOGIN:
                ui.label("Test sign-in (development only, synthetic people)").classes(
                    "text-sm text-grey-7"
                )
                ui.html(dev_sign_in_form(BACKEND_URL, "alex", "Test patient Alex"), sanitize=False)
                ui.html(
                    dev_sign_in_form(BACKEND_URL, "sam", "Second test patient Sam"), sanitize=False
                )
        else:
            heading(f"Hello, {me.user.display_name}")
            ui.label(describe_role(me)).classes("text-lg")
            if any(patient.role == "OWNER" for patient in me.patients):
                link_button("Upload discharge papers", "/upload")
                link_button("Check what we found", "/confirm", outline=True)
            ui.html(sign_out_form(BACKEND_URL), sanitize=False)
        footer()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host=UI_HOST,
        port=UI_PORT,
        title="AfterCare",
        reload=False,
        show=False,
        show_welcome_message=False,
    )
