from fastapi import Request
from nicegui import ui

from ui.api_client import BackendUnavailable, NotSignedIn, SummaryMedicine
from ui.backend import backend, session_token
from ui.components.basics import button, chip
from ui.components.shell import app_shell
from ui.content import confirmed_note, medicine_card_chip
from ui.layout import show_not_confirmed, show_server_down, signed_in_member

# The two sections where the papers say to get help carry a label in words, not just a color.
SECTION_CHIPS = {
    "call_911": ("Call 911", "CALL_911"),
    "call_care_team": ("Care team", "CALL_CARE_TEAM"),
}


def _medicine_card(index: int, medicine: SummaryMedicine) -> None:
    """One medicine in its own card: how to take it, and that the patient confirmed it."""
    with (
        ui.column()
        .classes("ac-card fade-up gap-2")
        .style(f"animation-delay:{min(index, 6) * 60}ms")
    ):
        with ui.row().classes("w-full items-start justify-between no-wrap gap-3"):
            with ui.column().classes("gap-0"):
                ui.label(medicine.name).classes("ac-h2")
                if medicine.other_names:
                    ui.label(f"Also called {', '.join(medicine.other_names)}").classes("ac-small")
            words = medicine_card_chip(medicine.status, medicine.as_needed)
            if words:
                chip(*words)
        stopped = medicine.status == "STOPPED"
        if not stopped:
            facts = [part for part in (medicine.dose, medicine.how_often) if part]
            if facts:
                ui.label(", ".join(facts)).classes("ac-lead")
            if medicine.end_date:
                ui.label(f"Last day: {medicine.end_date}").classes("ac-small")
        if medicine.note:
            ui.label(medicine.note)
        with ui.row().classes("w-full items-center gap-2"):
            chip("You confirmed this", "NEUTRAL", icon="check_circle")
            if medicine.source_page:
                ui.label(f"From your papers, page {medicine.source_page}").classes("ac-small")
        if not stopped:
            button(
                "Ask what it's for",
                kind="soft",
                arrow=False,
                href=f"/ask?about={index}",
            )


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

        if summary.medicines:
            with ui.column().classes("gap-1 fade-up"):
                ui.label("Your medicines").classes("ac-h2")
                ui.label(confirmed_note(summary.confirmed_at)).classes("ac-small")
            for index, medicine in enumerate(summary.medicines):
                _medicine_card(index, medicine)

        for index, section in enumerate(summary.sections):
            if section.key == "medicines" and summary.medicines:
                continue  # shown above, one card for each
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
