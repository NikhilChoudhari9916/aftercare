from typing import Any

from fastapi import Request
from nicegui import ui

from ui.api_client import BackendUnavailable, Draft, DraftItem, NotSignedIn, Rejected
from ui.content import (
    EDIT_FIELDS,
    SECTION_ORDER,
    SECTION_TITLES,
    SELECT_FIELDS,
    apply_edits,
    injection_warning,
    item_headline,
    item_lines,
    quote_note,
)
from ui.layout import (
    backend,
    footer,
    heading,
    link_button,
    page_column,
    session_token,
    show_server_down,
    signed_in_owner,
)

KEEP = "keep"
REMOVE = "remove"
DECISIONS = {KEEP: "Looks right", REMOVE: "Remove"}


@ui.page("/confirm")
async def confirm_page(request: Request) -> None:
    found = await signed_in_owner(request)
    if found is None:
        return
    _, patient = found
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
        show_confirmed(draft)
        return
    show_review(draft, patient.id, token)


def show_confirmed(draft: Draft) -> None:
    with page_column():
        heading("Your papers are confirmed")
        ui.label(
            f"You confirmed {len(draft.items)} items. "
            "Only confirmed items are ever used to answer your questions."
        ).classes("text-lg")
        ui.label("Your summary and medicine schedule are coming next.").classes("text-base")
        link_button("Upload different papers", "/upload", outline=True)
        link_button("Home", "/", outline=True)
        footer()


def show_review(draft: Draft, patient_id: str, token: str | None) -> None:
    decisions: dict[str, str | None] = {item.id: None for item in draft.items}
    toggles: dict[str, ui.toggle] = {}
    editors: dict[str, dict[str, Any]] = {}
    message = None

    def refresh() -> None:
        done = sum(1 for value in decisions.values() if value is not None)
        count.set_text(f"{done} of {len(decisions)} checked")
        confirm.set_enabled(done == len(decisions))

    def decide(item_id: str, card: ui.card, value: str | None) -> None:
        decisions[item_id] = value
        if value == REMOVE:
            card.classes(add="opacity-50")
        else:
            card.classes(remove="opacity-50")
        refresh()

    def mark_all_right() -> None:
        for item_id, toggle in toggles.items():
            if decisions[item_id] is None:
                toggle.set_value(KEEP)

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
            confirm.set_enabled(True)
        except NotSignedIn:
            ui.navigate.to("/")
        except BackendUnavailable:
            message.set_text("AfterCare can't reach its server right now. Please try again.")
            confirm.set_enabled(True)
        else:
            ui.navigate.to("/confirm")

    with page_column():
        heading("Check what we found")
        ui.label(
            "Below is what AfterCare read from your papers, next to the exact words it came from. "
            "For each item, choose “Looks right” or “Remove”. If something is a little off, "
            "open “Fix something” and change it. Nothing is used until you confirm it."
        ).classes("text-lg")
        warning = injection_warning([flag.page for flag in draft.injection_flags])
        if warning:
            ui.label(warning).classes("text-negative text-base").props('role="alert"')
        if draft.discharge_date:
            ui.label(f"Discharge date: {draft.discharge_date}").classes("text-base")

        for section in SECTION_ORDER:
            items = [item for item in draft.items if item.section == section]
            if not items:
                continue
            ui.label(SECTION_TITLES[section]).classes("text-2xl font-medium")
            for item in items:
                item_card(item, toggles, editors, decide)

        ui.button("Mark everything left as “Looks right”", on_click=mark_all_right).props(
            "outline no-caps color=primary"
        ).classes("w-full min-h-12")
        count = ui.label().classes("text-base").props('role="status"')
        message = ui.label().classes("text-negative text-base").props('role="alert"')
        confirm = (
            ui.button("Confirm", on_click=submit)
            .props("no-caps unelevated color=primary size=lg")
            .classes("w-full min-h-12")
        )
        link_button("Upload different papers", "/upload", outline=True)
        footer()
    refresh()


def item_card(item: DraftItem, toggles: dict, editors: dict, decide) -> None:
    data = item.data
    with ui.card().classes("w-full gap-2") as card:
        ui.label(item_headline(item.section, data)).classes("text-xl font-medium break-words")
        for line in item_lines(item.section, data):
            ui.label(line).classes("text-base")
        ui.label(f"From your papers, page {data.get('source_page', '?')}:").classes(
            "text-sm text-grey-7 mt-2"
        )
        ui.label(f"“{data.get('source_quote', '')}”").classes("text-base italic break-words")
        note = quote_note(item.quote_status)
        if note:
            ui.label(note).classes("text-negative text-base").props('role="alert"')

        toggle = (
            ui.toggle(
                DECISIONS, value=None, on_change=lambda e, i=item.id, c=card: decide(i, c, e.value)
            )
            .props(
                "no-caps unelevated color=white text-color=primary "
                "toggle-color=primary toggle-text-color=white"
            )
            .classes("border")
        )
        toggles[item.id] = toggle

        editors[item.id] = {}
        with ui.expansion("Fix something").classes("w-full"):
            select = SELECT_FIELDS.get(item.section)
            if select:
                key, options = select
                label = "Status" if key == "status" else "What to do"
                editors[item.id][key] = ui.select(
                    options, value=data.get(key), label=label
                ).classes("w-full")
            for key, label in EDIT_FIELDS[item.section]:
                editors[item.id][key] = ui.input(label, value=data.get(key) or "").classes("w-full")
