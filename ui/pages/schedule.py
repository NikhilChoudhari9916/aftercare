from fastapi import Request
from nicegui import ui

from ui.api_client import BackendUnavailable, MedicineLine, NotSignedIn, Schedule
from ui.backend import BACKEND_URL, backend, session_token
from ui.components.basics import alert, button, chip, tip
from ui.components.plan_form import plan_form
from ui.components.shell import app_shell
from ui.content import (
    CALENDAR_REDOWNLOAD,
    NEEDS_TIMING_NOTE,
    SCHEDULE_TIP,
    STATUS_WORDS,
    also_called,
    calendar_url,
    clock_label,
    end_date_note,
    medicine_title,
    visit_when_text,
)
from ui.layout import show_not_confirmed, show_server_down, signed_in_member


@ui.page("/schedule")
async def schedule_page(request: Request) -> None:
    found = await signed_in_member(request)
    if found is None:
        return
    me, patient = found
    try:
        schedule = await backend.get_schedule(session_token(request), patient.id)
    except NotSignedIn:
        ui.navigate.to("/")
        return
    except BackendUnavailable:
        show_server_down()
        return
    if schedule is None:
        show_not_confirmed(me, patient, "/schedule")
        return

    with app_shell(me, active="/schedule"):
        with ui.column().classes("gap-2 fade-up"):
            ui.label("Your medicine schedule").classes("ac-title")
            ui.label("Taken from your confirmed papers.").classes("ac-lead")
        tip(SCHEDULE_TIP)
        if patient.role == "OWNER":
            plan_form(schedule, patient.id, session_token(request))
        else:
            tip("The patient chooses the reminder times and what to do about each visit.")
        show_schedule(schedule)
        calendar_card(patient.id)
        button("Home", kind="ghost", href="/")


def medicine_row(line: MedicineLine, *, show_status: bool = False) -> None:
    with ui.column().classes("gap-0 w-full"):
        with ui.row().classes("w-full items-start justify-between no-wrap gap-3"):
            ui.label(medicine_title(line.name, line.dose)).classes("font-bold text-lg break-words")
            if show_status:
                chip(STATUS_WORDS.get(line.status, line.status), line.status)
        details = [
            also_called(line.other_names),
            line.how_often or None,
            end_date_note(line.end_date),
            "You chose this time" if line.chosen else None,
        ]
        for detail in filter(None, details):
            ui.label(detail).classes("ac-small")
        ui.label(f"From your papers, page {line.source_page}").classes("ac-small")


def show_schedule(schedule: Schedule) -> None:
    for dose_time in schedule.daily:
        with ui.column().classes("ac-card fade-up"):
            with ui.row().classes("items-center gap-3"):
                chip(clock_label(dose_time.time), "NEUTRAL", icon="schedule")
                ui.label(dose_time.label).classes("ac-h2")
            for line in dose_time.medicines:
                medicine_row(line)

    if schedule.needs_timing:
        with ui.column().classes("ac-card"):
            ui.label("Choose a time for these").classes("ac-h2")
            alert(NEEDS_TIMING_NOTE)
            for line in schedule.needs_timing:
                medicine_row(line)

    if schedule.as_needed:
        with ui.column().classes("ac-card"):
            ui.label("Only when needed").classes("ac-h2")
            ui.label("No calendar reminders for these.").classes("ac-small")
            for line in schedule.as_needed:
                medicine_row(line, show_status=True)

    if schedule.stopped:
        with ui.column().classes("ac-card"):
            ui.label("Stopped").classes("ac-h2")
            ui.label("Your papers say these are stopped. They are not on your schedule.").classes(
                "ac-small"
            )
            for line in schedule.stopped:
                medicine_row(line, show_status=True)

    if schedule.follow_ups:
        with ui.column().classes("ac-card"):
            ui.label("Visits and tests").classes("ac-h2")
            for visit in schedule.follow_ups:
                with ui.column().classes("gap-0 w-full"):
                    with ui.row().classes("w-full items-start justify-between no-wrap gap-3"):
                        ui.label(visit.what).classes("font-bold text-lg")
                        if visit.status == "NOT_BOOKED":
                            chip("Not booked yet", "CHANGED")
                        elif visit.in_calendar:
                            chip("In your calendar", "NEW")
                        else:
                            chip("Add this one yourself", "CHANGED")
                    ui.label(visit_when_text(visit)).classes("ac-small")
                    ui.label(
                        "Your choice"
                        if visit.chosen
                        else f"From your papers, page {visit.source_page}"
                    ).classes("ac-small")


def calendar_card(patient_id: str) -> None:
    with ui.column().classes("ac-card"):
        ui.label("Add reminders to your calendar").classes("ac-h2")
        ui.label(
            "The file works with Google, Apple and Outlook calendars. "
            "It makes reminders for the next 30 days, in your own time zone. "
            "Titles are private, like “Evening medicines”."
        )
        button("Download calendar file", href=calendar_url(BACKEND_URL, patient_id), icon="event")
        button(
            "Download with medicine names",
            kind="soft",
            href=calendar_url(BACKEND_URL, patient_id, "detailed"),
            icon="medication",
        )
        ui.label(CALENDAR_REDOWNLOAD).classes("ac-small")
