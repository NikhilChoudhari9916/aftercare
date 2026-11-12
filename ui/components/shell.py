from contextlib import contextmanager
from html import escape

from nicegui import ui

from ui.api_client import Me
from ui.backend import BACKEND_URL
from ui.components.basics import button
from ui.content import sign_in_url, sign_out_form


def _initial(me: Me) -> str:
    name = me.user.display_name.strip()
    return (name[:1] or "?").upper()


def _links(me: Me | None) -> list[tuple[str, str]]:
    if me is None:
        return [("How it works", "#how")]
    if any(patient.role == "OWNER" for patient in me.patients):
        return [
            ("Home", "/"),
            ("Upload", "/upload"),
            ("Review", "/confirm"),
            ("Summary", "/summary"),
            ("Schedule", "/schedule"),
        ]
    return [("Home", "/"), ("Summary", "/summary"), ("Schedule", "/schedule")]


def _nav(me: Me | None, active: str) -> None:
    """The floating glass pill at the top of every page."""
    with ui.header(fixed=True, elevated=False).classes("ac-header"):
        with ui.element("nav").classes("ac-nav"):
            with ui.link(target="/").classes("ac-logo"):
                ui.icon("health_and_safety").classes("text-3xl")
                ui.label("AfterCare").classes("ac-logo-text")
            with ui.element("div").classes("ac-nav-links"):
                for text, target in _links(me):
                    current = " is-current" if target == active else ""
                    ui.link(text, target).classes("ac-nav-link" + current)
            if me is None:
                button("Sign in", href=sign_in_url(BACKEND_URL), fit=True, compact=True)
            else:
                _account_menu(me)


def _account_menu(me: Me) -> None:
    label = f"Menu for {escape(me.user.display_name)}"
    with ui.button(color=None).props("round flat").props(f'aria-label="{label}"'):
        with ui.element("div").classes("ac-avatar"):
            ui.label(_initial(me))
        with ui.menu().props("auto-close"):
            for text, target in _links(me):
                ui.menu_item(text, on_click=lambda target=target: ui.navigate.to(target))
            ui.separator()
            with ui.element("div").classes("q-pa-sm").style("min-width:180px"):
                ui.html(sign_out_form(BACKEND_URL), sanitize=False).classes("w-full")


@contextmanager
def app_shell(me: Me | None = None, *, bar: bool = False, wide: bool = False, active: str = "/"):
    """The glass navigation pill, then a centered page. Everything on screen goes inside this."""
    _nav(me, active)
    classes = "ac-container" + (" has-bar" if bar else "") + (" wide" if wide else "")
    with ui.element("main").classes(classes) as container:
        yield container
        ui.label("Synthetic data only. Not medical advice.").classes("ac-small text-center")
