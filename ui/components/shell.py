from contextlib import contextmanager
from html import escape

from nicegui import ui

from ui.api_client import Me
from ui.backend import BACKEND_URL
from ui.content import sign_out_form


def _initial(me: Me) -> str:
    name = me.user.display_name.strip()
    return (name[:1] or "?").upper()


def _header(me: Me | None) -> None:
    with ui.header(fixed=True, elevated=False).classes("ac-header"):
        with ui.element("div").classes("ac-header-inner"):
            with ui.link(target="/").classes("ac-logo"):
                with ui.element("div").classes("ac-logo-badge"):
                    ui.icon("favorite").classes("text-xl")
                ui.label("AfterCare").classes("ac-logo-text")
            if me is not None:
                _account_menu(me)


def _account_menu(me: Me) -> None:
    is_owner = any(patient.role == "OWNER" for patient in me.patients)
    with (
        ui.button()
        .props("round flat")
        .props(f'aria-label="Menu for {escape(me.user.display_name)}"')
    ):
        with (
            ui.element("div")
            .classes("ac-icon-bubble")
            .style("width:40px;height:40px;border-radius:50%")
        ):
            ui.label(_initial(me)).classes("font-bold")
        with ui.menu().props("auto-close"):
            ui.menu_item("Home", on_click=lambda: ui.navigate.to("/"))
            if is_owner:
                ui.menu_item("Upload papers", on_click=lambda: ui.navigate.to("/upload"))
                ui.menu_item("Check what we found", on_click=lambda: ui.navigate.to("/confirm"))
            ui.separator()
            with ui.element("div").classes("q-pa-sm").style("min-width:180px"):
                ui.html(sign_out_form(BACKEND_URL), sanitize=False).classes("w-full")


@contextmanager
def app_shell(me: Me | None = None, *, bar: bool = False):
    """The header, then a centered one-column page. Everything on screen goes inside this."""
    _header(me)
    with ui.element("main").classes("ac-container" + (" has-bar" if bar else "")) as container:
        yield container
        ui.label("Synthetic data only. Not medical advice.").classes("ac-small text-center")
