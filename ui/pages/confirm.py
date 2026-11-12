from typing import Any

from fastapi import Request
from nicegui import ui

from ui.api_client import BackendUnavailable, Draft, DraftItem, Me, NotSignedIn, Rejected
from ui.backend import backend, session_token
from ui.components.art import success_check
from ui.components.basics import alert, button, chip, tip
from ui.components.decision import KEEP, REMOVE, Decision
from ui.components.shell import app_shell
from ui.content import (
    EDIT_FIELDS,
    SECTION_ORDER,
    SECTION_TITLES,
    SELECT_FIELDS,
    apply_edits,
    injection_warning,
    item_chip,
    item_headline,
    item_lines,
    quote_note,
)
from ui.layout import show_server_down, signed_in_owner


@ui.page("/confirm")
async def confirm_page(request: Request) -> None:
    found = await signed_in_owner(request)
    if found is None:
        return
    me, patient = found
    token = session_token(request)

    try:
        draft = await backend.get_draft(token, patient.id)
    except NotSignedIn:
        ui.navigate.to("/")
        return
    except BackendUnavailable:
        show_server_down()
        return
    if draft is None:
        ui.navigate.to("/upload")
        return
    if draft.status == "CONFIRMED":
        show_confirmed(me, draft)
        return
    show_review(me, draft, patient.id, token)


def show_confirmed(me: Me, draft: Draft) -> None:
    with app_shell(me):
        with ui.column().classes("ac-card ac-hero fade-up"):
            success_check()
            ui.label("Your papers are confirmed").classes("ac-title")
            ui.label(
                f"You confirmed {len(draft.items)} items. "
                "Only confirmed items are ever used to answer your questions."
            ).classes("ac-lead")
            tip("Your summary and medicine schedule are coming next.")
        button("Upload different papers", kind="ghost", href="/upload")
        button("Home", kind="ghost", href="/")


def show_review(me: Me, draft: Draft, patient_id: str, token: str | None) -> None:
    total = len(draft.items)
    decisions: dict[str, str | None] = {item.id: None for item in draft.items}
    choices: dict[str, Decision] = {}
    editors: dict[str, dict[str, Any]] = {}

    def refresh() -> None:
        done = sum(1 for value in decisions.values() if value is not None)
        count.set_text(f"{done} of {total} checked")
        ring.set_value(done)
        confirm.set_enabled(done == total)

    def decide(item_id: str, card: ui.element, value: str | None) -> None:
        decisions[item_id] = value
        if value == REMOVE:
            card.classes(add="is-removed")
        else:
            card.classes(remove="is-removed")
        refresh()

    def mark_all_right() -> None:
        for item_id, choice in choices.items():
            if decisions[item_id] is None:
                choice.set_value(KEEP)

    async def submit() -> None:
        confirm.set_enabled(False)
        payload: list[dict[str, Any]] = []
        for item in draft.items:
            if decisions[item.id] == REMOVE:
                payload.append({"id": item.id, "action": "remove"})
                continue
            entry: dict[str, Any] = {"id": item.id, "action": "confirm"}
            edits = {key: widget.value for key, widget in editors[item.id].items()}
            changed = apply_edits(item.data, edits)
            if changed is not None:
                entry["data"] = changed
            payload.append(entry)
        try:
            await backend.confirm_profile(token, patient_id, draft.version_id, payload)
        except Rejected as error:
            message.set_text(str(error))
            message.set_visibility(True)
            confirm.set_enabled(True)
        except NotSignedIn:
            ui.navigate.to("/")
        except BackendUnavailable:
            message.set_text("AfterCare can't reach its server right now. Please try again.")
            message.set_visibility(True)
            confirm.set_enabled(True)
        else:
            ui.navigate.to("/confirm")

    # The sticky bar must be created outside the page column, directly in the page.
    with ui.footer(fixed=True).classes("ac-bar"):
        with ui.element("div").classes("ac-bar-inner"):
            ring = ui.circular_progress(
                value=0, min=0, max=total, size="44px", show_value=False, color="primary"
            ).props('track-color="grey-3" thickness=0.22')
            count = ui.label().classes("ac-bar-count").props('role="status"')
            confirm = button("Confirm", icon="done_all", on_click=submit).style("flex:1")

    with app_shell(me, bar=True):
        with ui.column().classes("gap-2 fade-up"):
            ui.label("Check what we found").classes("ac-title")
            ui.label(
                "Here is what AfterCare read, next to the exact words from your papers. "
                "Nothing is used until you confirm it."
            ).classes("ac-lead")
        tip(
            "For each item, tap “Looks right” or “Remove”. "
            "If something is a little off, open “Fix it”."
        )
        warning = injection_warning([flag.page for flag in draft.injection_flags])
        if warning:
            alert(warning)
        if draft.discharge_date:
            ui.label(f"Discharge date: {draft.discharge_date}").classes("ac-small")

        for section in SECTION_ORDER:
            items = [item for item in draft.items if item.section == section]
            if not items:
                continue
            with ui.row().classes("items-center gap-2 mt-2"):
                ui.label(SECTION_TITLES[section]).classes("ac-h2")
                chip(str(len(items)), "NEUTRAL")
            for index, item in enumerate(items):
                item_card(item, index, choices, editors, decide)

        button(
            "Mark everything left as “Looks right”",
            kind="soft",
            icon="done_all",
            on_click=mark_all_right,
        )
        message = alert("")
        message.set_visibility(False)
        button("Upload different papers", kind="ghost", href="/upload")
    refresh()


def item_card(item: DraftItem, index: int, choices: dict, editors: dict, decide) -> None:
    data = item.data
    with (
        ui.column()
        .classes("ac-card fade-up")
        .style(f"animation-delay:{min(index, 6) * 60}ms") as card
    ):
        with ui.row().classes("w-full items-start justify-between no-wrap gap-3"):
            ui.label(item_headline(item.section, data)).classes("font-bold text-xl break-words")
            status = item_chip(item.section, data)
            if status:
                chip(status[0], status[1])
        for line in item_lines(item.section, data):
            ui.label(line)
        with ui.column().classes("ac-quote gap-1"):
            ui.label(f"From your papers, page {data.get('source_page', '?')}").classes(
                "ac-quote-label"
            )
            ui.label(f"“{data.get('source_quote', '')}”")
        note = quote_note(item.quote_status)
        if note:
            alert(note)

        choices[item.id] = Decision(lambda value, i=item.id, c=card: decide(i, c, value))

        editors[item.id] = {}
        with ui.expansion("Fix it", icon="edit").classes("ac-fix w-full"):
            select = SELECT_FIELDS.get(item.section)
            if select:
                key, options = select
                label = "Status" if key == "status" else "What to do"
                editors[item.id][key] = ui.select(
                    options, value=data.get(key), label=label
                ).classes("w-full")
            for key, label in EDIT_FIELDS[item.section]:
                editors[item.id][key] = ui.input(label, value=data.get(key) or "").classes("w-full")
