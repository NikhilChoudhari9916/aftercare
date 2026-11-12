from nicegui import ui

from ui.content import PROGRESS_STEPS, step_states

ICONS = {"done": "check", "active": "autorenew", "pending": "circle"}


class StepTracker:
    """The friendly "what is happening now" list shown while a document is being read."""

    def __init__(self) -> None:
        self._rows: list[tuple[ui.element, ui.icon]] = []
        with ui.column().classes("gap-4 w-full").props('role="status" aria-live="polite"'):
            for _, words in PROGRESS_STEPS:
                row = ui.element("div").classes("ac-step is-pending")
                with row:
                    with ui.element("div").classes("ac-step-dot"):
                        icon = ui.icon(ICONS["pending"]).classes("text-xl")
                    ui.label(words).classes("ac-step-text")
                self._rows.append((row, icon))

    def update(self, status: str, step: str | None) -> None:
        for (row, icon), state in zip(self._rows, step_states(status, step), strict=True):
            row.classes(
                remove="is-pending is-active is-done",
                add=f"is-{state}",
            )
            icon.props(f"name={ICONS[state]}")
            icon.classes(remove="ac-spin", add="ac-spin" if state == "active" else "")
