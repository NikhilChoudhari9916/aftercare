from collections.abc import Callable

from nicegui import ui

from ui.theme import CHIP_COLORS


def button(
    text: str,
    *,
    kind: str = "primary",
    icon: str | None = None,
    href: str | None = None,
    on_click: Callable | None = None,
) -> ui.button:
    """kind is "primary", "soft", or "ghost". A button with an href is a real link."""
    widget = ui.button(text, icon=icon, color=None, on_click=on_click)
    widget.props("unelevated no-caps")
    if href:
        widget.props(f'href="{href}"')
    return widget.classes(f"ac-btn ac-btn-{kind}")


def chip(label: str, kind: str = "NEUTRAL", icon: str | None = None) -> ui.element:
    """A small colored label. The words always say what the color means."""
    background, text = CHIP_COLORS.get(kind, CHIP_COLORS["NEUTRAL"])
    with ui.element("span").classes("ac-chip").style(f"background:{background};color:{text}") as el:
        if icon:
            ui.icon(icon).classes("text-base")
        ui.label(label)
    return el


def alert(text: str) -> ui.label:
    return ui.label(text).classes("ac-alert").props('role="alert"')


def tip(text: str) -> ui.label:
    return ui.label(text).classes("ac-tip")


def icon_bubble(name: str, *, warm: bool = False) -> None:
    with ui.element("div").classes("ac-icon-bubble" + (" warm" if warm else "")):
        ui.icon(name).classes("text-2xl")
