from fastapi import Request
from nicegui import ui

from ui.api_client import BackendUnavailable, NotSignedIn
from ui.backend import backend, session_token
from ui.components.basics import button, chip
from ui.components.shell import app_shell
from ui.layout import show_not_confirmed, show_server_down, signed_in_member

# The two sections where the papers say to get help carry a label in words, not just a color.
SECTION_CHIPS = {
    "call_911": ("Call 911", "CALL_911"),
    "call_care_team": ("Care team", "CALL_CARE_TEAM"),
}


@ui.page("/summary")
async def summary_page(request: Request) -> None:
    found = await signed_in_member(request)
    if found is None:
        return
    me, patient = found
    try:
        summary = await backend.get_summary(session_token(request), patient.id)
    except NotSignedIn:
        ui.navigate.to("/")
        return
    except BackendUnavailable:
        show_server_down()
        return
    if summary is None:
        show_not_confirmed(me, patient, "/summary")
        return

    with app_shell(me, active="/summary"):
        with ui.column().classes("gap-2 fade-up"):
            ui.label("Your summary").classes("ac-title")
            ui.label(summary.intro).classes("ac-lead")

        for index, section in enumerate(summary.sections):
            with (
                ui.column()
                .classes("ac-card fade-up")
                .style(f"animation-delay:{min(index, 6) * 60}ms")
            ):
                with ui.row().classes("w-full items-center justify-between no-wrap gap-3"):
                    ui.label(section.title).classes("ac-h2")
                    label = SECTION_CHIPS.get(section.key)
                    if label:
                        chip(*label)
                for line in section.lines:
                    with ui.column().classes("gap-0"):
                        ui.label(line.text)
                        if line.source_page:
                            ui.label(f"From your papers, page {line.source_page}").classes(
                                "ac-small"
                            )

        button("See your schedule", href="/schedule")
        button("Home", kind="ghost", href="/")
