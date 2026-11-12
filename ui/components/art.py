# ruff: noqa: E501  (this file is CSS/SVG text; long lines are normal there)
from nicegui import ui

# A hand-drawn inline picture, so the pages load nothing from outside.
CHECK_SVG = """
<svg viewBox="0 0 80 80" width="96" height="96" role="img" aria-label="Done">
  <circle class="ac-check-circle" cx="40" cy="40" r="30" fill="#E3F2EC" stroke="#23705F" stroke-width="4"/>
  <path class="ac-check-tick" d="M27 41l9 9 18-20" fill="none" stroke="#23705F" stroke-width="5"
        stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


def success_check() -> ui.html:
    return ui.html(CHECK_SVG, sanitize=False)


# Made-up example rows for the landing page preview. Not real people or real medicines lists.
PREVIEW_ROWS = (
    ("8:00 AM", "Furosemide 40 mg", "Changed", "CHANGED"),
    ("8:00 PM", "Metoprolol 25 mg", "New", "NEW"),
    ("Only if needed", "Acetaminophen 500 mg", "Only when needed", "AS_NEEDED"),
)


def preview_card() -> None:
    """A glass "Today" card that shows what the finished product will feel like."""
    from ui.components.basics import chip

    with ui.column().classes("ac-glass-card ac-preview"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Today").classes("ac-h2")
            ui.label("Example data").classes("ac-eyebrow")
        for time, name, words, kind in PREVIEW_ROWS:
            with ui.element("div").classes("ac-preview-row"):
                with ui.column().classes("gap-0"):
                    ui.label(time).classes("ac-preview-time text-sm")
                    ui.label(name).classes("font-semibold")
                chip(words, kind)
        with ui.element("div").classes("ac-preview-row"):
            ui.label("Next visit: Tuesday 10:30 AM").classes("font-semibold")
            ui.icon("event").classes("text-xl")
