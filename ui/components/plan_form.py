"""The "Set up your reminders" form: reminder times for every medicine, and a plan for every visit.

One form, one Save button (ADR-0042). The page only collects what the patient typed; the server
checks every rule and answers in plain language.
"""

from nicegui import ui

from ui.api_client import (
    BackendUnavailable,
    FollowUpLine,
    MedicineLine,
    NotSignedIn,
    Rejected,
    Schedule,
)
from ui.backend import backend
from ui.components.basics import alert, button, chip
from ui.content import (
    BOOKED,
    NOT_BOOKED,
    PLAN_INTRO,
    PLAN_SAVED,
    VISIT_KIND_NOTES,
    also_called,
    build_plan_payload,
    medicine_title,
    times_note,
    visit_start_state,
    visit_when,
)

MAX_TIMES = 6  # the server's limit, so the page does not offer more boxes than it will accept
SEPARATOR = "border-top:1px solid var(--line)"


def _time_box(value: str, label: str) -> ui.input:
    # A native time or date box: phones show their own easy picker.
    return ui.input(label, value=value).props("type=time outlined stack-label").classes("w-full")


def _date_box(value: str, label: str) -> ui.input:
    return ui.input(label, value=value).props("type=date outlined stack-label").classes("w-full")


def _medicine_times(line: MedicineLine, boxes: dict[str, list[ui.input]]) -> None:
    """The time boxes for one medicine: fixed when the papers are clear, open when they are not."""
    boxes[line.item_id] = []
    fixed = line.times_needed
    with ui.column().classes("w-full gap-2 pt-3").style(SEPARATOR):
        ui.label(medicine_title(line.name, line.dose)).classes("font-bold text-lg break-words")
        for detail in filter(None, [also_called(line.other_names), line.how_often or None]):
            ui.label(detail).classes("ac-small")
        ui.label(times_note(fixed)).classes("ac-small")
        holder = ui.column().classes("w-full gap-2")

        def add(value: str = "") -> None:
            with holder:
                with ui.row().classes("w-full items-center no-wrap gap-2") as row:
                    number = len(boxes[line.item_id]) + 1
                    box = _time_box(value, f"Time {number}")
                    if fixed is None:
                        ui.button(
                            icon="close", color=None, on_click=lambda: remove(row, box)
                        ).props('flat round aria-label="Remove this time"').classes("ac-plan-small")
            boxes[line.item_id].append(box)
            add_button.set_visibility(fixed is None and len(boxes[line.item_id]) < MAX_TIMES)

        def remove(row: ui.element, box: ui.input) -> None:
            boxes[line.item_id].remove(box)
            holder.remove(row)
            add_button.set_visibility(len(boxes[line.item_id]) < MAX_TIMES)

        add_button = (
            ui.button("Add a time", icon="add", color=None, on_click=lambda: add())
            .props("flat no-caps")
            .classes("ac-plan-small")
        )
        initial = line.times if fixed is None else (line.times + [""] * fixed)[:fixed]
        for value in initial:
            add(value)
        add_button.set_visibility(fixed is None and len(initial) < MAX_TIMES)


def _visit(line: FollowUpLine, states: dict[str, dict]) -> None:
    start = visit_start_state(line)
    with ui.column().classes("w-full gap-2 pt-3").style(SEPARATOR):
        with ui.row().classes("w-full items-start justify-between no-wrap gap-3"):
            ui.label(line.what).classes("font-bold text-lg break-words")
            chip("Booked or not?", "NEUTRAL")
        ui.label(f"Your papers say: {visit_when(line.when, line.with_whom)}").classes("ac-small")
        ui.label(VISIT_KIND_NOTES.get(line.kind, "")).classes("ac-small")

        choice = (
            ui.toggle(
                {BOOKED: "I have a date", NOT_BOOKED: "Not booked yet"}, value=start["status"]
            )
            .props("no-caps unelevated")
            .classes("ac-plan-toggle")
        )
        with (
            ui.column()
            .classes("w-full gap-2")
            .bind_visibility_from(choice, "value", backward=lambda value: value == BOOKED)
        ):
            day = _date_box(start["date"], "Date of the visit")
            clock = _time_box(start["time"], "Time (if you know it)")
        with (
            ui.column()
            .classes("w-full gap-2")
            .bind_visibility_from(choice, "value", backward=lambda value: value == NOT_BOOKED)
        ):
            ui.label("You still need to call to book it.").classes("ac-small")
            call_on = _date_box(start["call_on"], "Remind me to call on")
    states[line.item_id] = {"status": choice, "date": day, "time": clock, "call_on": call_on}


def plan_form(schedule: Schedule, patient_id: str, token: str | None) -> None:
    medicine_boxes: dict[str, list[ui.input]] = {}
    visit_widgets: dict[str, dict] = {}

    async def save() -> None:
        save_button.set_enabled(False)
        message.set_visibility(False)
        payload = build_plan_payload(
            {
                item_id: [box.value or "" for box in boxes]
                for item_id, boxes in medicine_boxes.items()
            },
            {
                item_id: {key: widget.value or "" for key, widget in widgets.items()}
                for item_id, widgets in visit_widgets.items()
            },
        )
        try:
            await backend.save_plan(token, patient_id, payload)
        except Rejected as error:
            message.set_text(str(error))
            message.set_visibility(True)
            save_button.set_enabled(True)
        except NotSignedIn:
            ui.navigate.to("/")
        except BackendUnavailable:
            message.set_text("AfterCare can't reach its server right now. Please try again.")
            message.set_visibility(True)
            save_button.set_enabled(True)
        else:
            done.set_text(PLAN_SAVED)
            done.set_visibility(True)
            ui.timer(1.2, ui.navigate.reload, once=True)

    with ui.column().classes("ac-card fade-up").props("id=plan"):
        ui.label("Set up your reminders").classes("ac-h2")
        ui.label(PLAN_INTRO)

        if schedule.plan_medicines:
            ui.label("When you take your medicines").classes("font-bold text-lg")
            for line in schedule.plan_medicines:
                _medicine_times(line, medicine_boxes)
        if schedule.follow_ups:
            ui.label("Your visits and tests").classes("font-bold text-lg pt-3")
            for line in schedule.follow_ups:
                _visit(line, visit_widgets)

        message = alert("")
        message.set_visibility(False)
        done = ui.label("").classes("ac-tip").props('role="status"')
        done.set_visibility(False)
        save_button = button("Save my reminders", on_click=save)
