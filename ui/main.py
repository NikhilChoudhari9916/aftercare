import os
from urllib.parse import urlsplit

from fastapi import Request
from nicegui import app, ui

from ui.api_client import BackendUnavailable, Me
from ui.backend import BACKEND_URL, backend, session_token
from ui.components.art import hero_picture
from ui.components.basics import alert, button, chip, icon_bubble
from ui.components.shell import app_shell
from ui.content import HOW_IT_WORKS, describe_role, dev_sign_in_form, error_message, sign_in_url
from ui.layout import show_server_down
from ui.pages import confirm, upload  # noqa: F401  (importing registers the pages)
from ui.security import SecurityHeadersMiddleware
from ui.theme import apply_theme

# ui/ never imports from app/, so it reads the few settings it needs itself.
UI_URL = os.environ.get("UI_URL", "http://localhost:8080")
UI_HOST = os.environ.get("UI_HOST", "127.0.0.1")
UI_PORT = urlsplit(UI_URL).port or 8080
DEV_LOGIN = os.environ.get("DEV_LOGIN", "").lower() in {"1", "true", "yes"}

app.add_middleware(SecurityHeadersMiddleware)


@ui.page("/")
async def home(request: Request, error: str | None = None) -> None:
    apply_theme()
    try:
        me = await backend.me(session_token(request))
    except BackendUnavailable:
        show_server_down()
        return

    with app_shell(me):
        if me is None:
            signed_out(error)
        else:
            signed_in(me)


def signed_out(error: str | None) -> None:
    with ui.column().classes("ac-card ac-hero fade-up"):
        hero_picture()
        ui.label("Your hospital papers, in plain words").classes("ac-title")
        ui.label(
            "Understand what each medicine is for, when to take it, "
            "and what to do while you recover at home."
        ).classes("ac-lead")
        message = error_message(error)
        if message:
            alert(message)
        button("Sign in with Google", icon="login", href=sign_in_url(BACKEND_URL))
        if DEV_LOGIN:
            ui.label("Test sign-in (development only, synthetic people)").classes("ac-small")
            ui.html(
                dev_sign_in_form(BACKEND_URL, "alex", "Test patient Alex"), sanitize=False
            ).classes("w-full")
            ui.html(
                dev_sign_in_form(BACKEND_URL, "sam", "Second test patient Sam"), sanitize=False
            ).classes("w-full")
    with ui.column().classes("gap-3 w-full"):
        for index, (icon, title, text, soon) in enumerate(HOW_IT_WORKS):
            with (
                ui.row()
                .classes("ac-card fade-up items-center no-wrap")
                .style(f"animation-delay:{120 + index * 90}ms; flex-direction:row")
            ):
                icon_bubble(icon, warm=index == 1)
                with ui.column().classes("gap-0"):
                    ui.label(title).classes("font-bold")
                    ui.label(text).classes("ac-small")
                if soon:
                    chip("Coming soon", "NEUTRAL")


def signed_in(me: Me) -> None:
    first_name = me.user.display_name.split(" ")[0]
    with ui.column().classes("gap-1 fade-up"):
        ui.label(f"Hello, {first_name}").classes("ac-title")
        ui.label(describe_role(me)).classes("ac-lead")
    if not any(patient.role == "OWNER" for patient in me.patients):
        return
    actions = (
        ("upload_file", "Upload your papers", "Start with your discharge PDF", "/upload", False),
        (
            "fact_check",
            "Check what we found",
            "Review each item next to your papers",
            "/confirm",
            True,
        ),
    )
    for index, (icon, title, text, target, warm) in enumerate(actions):
        with (
            ui.link(target=target)
            .classes("ac-action fade-up")
            .style(f"animation-delay:{index * 90}ms")
        ):
            with ui.row().classes("ac-card no-wrap").style("flex-direction:row"):
                icon_bubble(icon, warm=warm)
                with ui.column().classes("gap-0 grow"):
                    ui.label(title).classes("font-bold text-lg")
                    ui.label(text).classes("ac-small")
                ui.icon("chevron_right").classes("text-2xl ac-soft")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host=UI_HOST,
        port=UI_PORT,
        title="AfterCare",
        reload=False,
        show=False,
        show_welcome_message=False,
    )
