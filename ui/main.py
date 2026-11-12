import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Request
from nicegui import app, ui

from ui.api_client import BackendUnavailable, Me
from ui.backend import BACKEND_URL, backend, session_token
from ui.components.art import preview_card
from ui.components.basics import alert, button, chip, icon_bubble
from ui.components.shell import app_shell
from ui.content import HOW_IT_WORKS, describe_role, dev_sign_in_form, error_message, sign_in_url
from ui.layout import show_server_down
from ui.pages import (  # noqa: F401  (importing registers the pages)
    confirm,
    schedule,
    summary,
    upload,
)
from ui.security import SecurityHeadersMiddleware
from ui.theme import apply_theme

# ui/ never imports from app/, so it reads the few settings it needs itself.
UI_URL = os.environ.get("UI_URL", "http://localhost:8080")
UI_HOST = os.environ.get("UI_HOST", "127.0.0.1")
UI_PORT = urlsplit(UI_URL).port or 8080
DEV_LOGIN = os.environ.get("DEV_LOGIN", "").lower() in {"1", "true", "yes"}

app.add_middleware(SecurityHeadersMiddleware)
app.add_static_files("/static", Path(__file__).parent / "static")  # our own font, nothing external

# Open to the patient and to an aide (an aide may read, ADR-0032).
READ_ACTIONS = (
    ("article", "Your summary", "Your papers in plain words", "/summary", False),
    (
        "event_available",
        "Your schedule",
        "Medicines by time, and a calendar file",
        "/schedule",
        True,
    ),
)

# Little round icons on the badge, like the row of faces in the reference design.
BADGE_ICONS = (("favorite", "#FFB3A3"), ("medication", "#9FE7CF"), ("event", "#FFD98A"))


@ui.page("/")
async def home(request: Request, error: str | None = None) -> None:
    apply_theme()
    try:
        me = await backend.me(session_token(request))
    except BackendUnavailable:
        show_server_down()
        return

    with app_shell(me, wide=me is None, active="/"):
        if me is None:
            signed_out(error)
        else:
            signed_in(me)


def signed_out(error: str | None) -> None:
    with ui.element("section").classes("ac-panel fade-up"):
        with ui.element("div").classes("ac-panel-copy"):
            with ui.element("div").classes("ac-badge"):
                with ui.element("div").classes("ac-avatars"):
                    for icon, color in BADGE_ICONS:
                        with ui.element("span").style(f"background:{color}"):
                            ui.icon(icon).classes("text-base")
                ui.label("Plain-language help for your first 30 days home")
            ui.label("Understand your hospital papers, in plain words").classes("ac-title")
            ui.label(
                "Upload your discharge papers and check each medicine and detail "
                "against your own words, step by step."
            ).classes("ac-lead").style("max-width:32rem")
            message = error_message(error)
            if message:
                alert(message)
            button("Sign in with Google", href=sign_in_url(BACKEND_URL), fit=True)
            if DEV_LOGIN:
                ui.label("Test sign-in (development only, synthetic people)").classes("ac-small")
                with ui.row().classes("w-full gap-3 no-wrap").style("max-width:30rem"):
                    for persona, label in (
                        ("alex", "Test patient Alex"),
                        ("sam", "Test patient Sam"),
                    ):
                        ui.html(
                            dev_sign_in_form(BACKEND_URL, persona, label), sanitize=False
                        ).classes("w-full")
        preview_card()

    with ui.element("section").classes("w-full gap-4 mt-6").props("id=how"):
        ui.label("How it works").classes("ac-eyebrow")
        ui.label("Three calm steps").classes("ac-title").style("font-size:clamp(1.8rem,5vw,2.6rem)")
        with ui.element("div").classes("grid gap-4 w-full sm:grid-cols-3 mt-2"):
            for index, (icon, title, text, soon) in enumerate(HOW_IT_WORKS):
                with (
                    ui.column()
                    .classes("ac-glass-card fade-up")
                    .style(f"animation-delay:{index * 90}ms")
                ):
                    with ui.row().classes("w-full items-center justify-between"):
                        icon_bubble(icon, warm=index == 1)
                        ui.label(f"0{index + 1}").classes("ac-step-number")
                    ui.label(title).classes("font-bold text-lg")
                    ui.label(text).classes("ac-small")
                    if soon:
                        chip("Coming soon", "NEUTRAL")


def signed_in(me: Me) -> None:
    first_name = me.user.display_name.split(" ")[0]
    with ui.column().classes("gap-2 fade-up"):
        ui.label(f"Hello, {first_name}").classes("ac-title")
        ui.label(describe_role(me)).classes("ac-lead")
    is_owner = any(patient.role == "OWNER" for patient in me.patients)
    owner_actions = (
        ("upload_file", "Upload your papers", "Start with your discharge PDF", "/upload", False),
        (
            "fact_check",
            "Check what we found",
            "Review each item next to your papers",
            "/confirm",
            True,
        ),
    )
    actions = (*(owner_actions if is_owner else ()), *READ_ACTIONS)
    for index, (icon, title, text, target, warm) in enumerate(actions):
        with (
            ui.link(target=target)
            .classes("ac-action fade-up")
            .style(f"animation-delay:{index * 90}ms")
        ):
            with ui.row().classes("ac-glass-card no-wrap"):
                icon_bubble(icon, warm=warm)
                with ui.column().classes("gap-0 grow"):
                    ui.label(title).classes("font-bold text-lg")
                    ui.label(text).classes("ac-small")
                with ui.element("span").classes("ac-arrow"):
                    ui.icon("arrow_forward").classes("text-lg")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host=UI_HOST,
        port=UI_PORT,
        title="AfterCare",
        reload=False,
        show=False,
        show_welcome_message=False,
    )
