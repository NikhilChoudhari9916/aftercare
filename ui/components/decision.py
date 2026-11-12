from collections.abc import Callable

from nicegui import ui

KEEP = "keep"
REMOVE = "remove"


class Decision:
    """Two big buttons: "Looks right" or "Remove". Nothing is chosen until the patient taps one."""

    def __init__(self, on_change: Callable[[str | None], None]) -> None:
        self.value: str | None = None
        self._on_change = on_change
        with ui.row().classes("ac-choice-row"):
            self._keep = (
                ui.button(
                    "Looks right", icon="check", color=None, on_click=lambda: self.set_value(KEEP)
                )
                .props("unelevated no-caps")
                .classes("ac-choice")
            )
            self._remove = (
                ui.button(
                    "Remove", icon="close", color=None, on_click=lambda: self.set_value(REMOVE)
                )
                .props("unelevated no-caps")
                .classes("ac-choice")
            )
        self._refresh()

    def set_value(self, value: str | None) -> None:
        self.value = value
        self._refresh()
        self._on_change(value)

    def _refresh(self) -> None:
        for button, mine, style in (
            (self._keep, KEEP, "is-keep"),
            (self._remove, REMOVE, "is-remove"),
        ):
            selected = self.value == mine
            button.classes(add=style) if selected else button.classes(remove=style)
            button.props(f"aria-pressed={'true' if selected else 'false'}")
