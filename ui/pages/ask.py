from collections.abc import Awaitable, Callable

from fastapi import Request
from nicegui import ui

from ui.api_client import Answer, BackendUnavailable, NotSignedIn, Rejected
from ui.backend import backend, session_token
from ui.components.basics import alert, button, chip
from ui.components.shell import app_shell
from ui.content import (
    ASK_DISCLAIMER,
    ASK_EXAMPLES,
    ASK_INTRO,
    ASK_UNAVAILABLE,
    ASK_WAITING,
    EMERGENCY_BANNER,
    MAX_QUESTION_CHARS,
    answer_html,
    citation_labels,
)
from ui.layout import show_not_confirmed, show_server_down, signed_in_member

# The question box is a plain browser text field, not a Quasar input: Quasar draws its fields for
# a white page, and on this dark theme that left the box black. It sits on a white card with a
# dark green border, so it is easy to see where to type.
BOX_STYLE = (
    "width:100%;min-height:64px;padding:0 20px;border-radius:14px;border:3px solid #14543F;"
    "background:#FFFFFF !important;color:#111111 !important;caret-color:#111111;"
    "font-size:1.15rem;outline:none;box-sizing:border-box"
)
BOX_ID = "ask-box"
READ_AND_CLEAR_JS = (
    "(() => { const box = document.getElementById('" + BOX_ID + "'); "
    "const text = box ? box.value : ''; "
    "if (box) { box.value = ''; box.focus(); } return text; })()"
)


def _emergency_banner() -> None:
    """Always on screen: it stays under the menu while the conversation scrolls."""
    with ui.element("div").classes("ac-card w-full").style("position:sticky;top:5.5rem;z-index:5"):
        with ui.row().classes("w-full items-center justify-between no-wrap gap-3"):
            ui.label(EMERGENCY_BANNER).classes("font-bold")
            button("Call 911", href="tel:911", fit=True, compact=True)


def _question_bubble(text: str) -> None:
    ui.label(text).classes("ac-glass-card").style("align-self:flex-end;max-width:90%")


def _answer_card(answer: Answer, on_followup: Callable[[str], Awaitable[None]]) -> None:
    emergency = answer.outcome == "emergency"
    with ui.column().classes("ac-card fade-up w-full gap-3"):
        if emergency:
            chip("Call 911", "CALL_911")
        elif answer.tier == 2:
            chip("Call your care team", "CALL_CARE_TEAM")
        labels = {} if emergency else citation_labels(answer.citations)
        ui.html(answer_html(answer.answer, labels), sanitize=False).classes("ac-lead")
        if emergency:
            button("Call 911", href="tel:911", fit=True)
        if answer.followups:
            with ui.row().classes("w-full gap-2"):
                for question in answer.followups:
                    button(
                        question,
                        kind="soft",
                        arrow=False,
                        on_click=lambda asked=question: on_followup(asked),
                    )
        ui.label(ASK_DISCLAIMER).classes("ac-small")


@ui.page("/ask")
async def ask_page(request: Request) -> None:
    found = await signed_in_member(request)
    if found is None:
        return
    me, patient = found
    token = session_token(request)
    try:
        summary = await backend.get_summary(token, patient.id)  # is anything confirmed yet?
    except NotSignedIn:
        ui.navigate.to("/")
        return
    except BackendUnavailable:
        show_server_down()
        return
    if summary is None:
        show_not_confirmed(me, patient, "/ask")
        return

    busy = {"on": False}

    with app_shell(me, active="/ask"):
        with ui.column().classes("gap-2 fade-up"):
            ui.label("Ask a question").classes("ac-title")
            ui.label(ASK_INTRO).classes("ac-lead")
        _emergency_banner()
        thread = ui.column().classes("w-full gap-3")

        async def send(text: str) -> None:
            asked = text.strip()
            if not asked or busy["on"]:
                return
            busy["on"] = True
            with thread:
                _question_bubble(asked)
                waiting = ui.label(ASK_WAITING).classes("ac-small")
            answer: Answer | None = None
            problem: str | None = None
            try:
                answer = await backend.ask(token, patient.id, asked)
            except NotSignedIn:
                ui.navigate.to("/")
            except Rejected as error:
                problem = str(error)
            except BackendUnavailable:
                problem = ASK_UNAVAILABLE
            waiting.delete()
            busy["on"] = False
            with thread:
                if answer is not None:
                    _answer_card(answer, send)
                elif problem:
                    alert(problem)

        async def send_typed() -> None:
            if busy["on"]:
                return
            typed = await ui.run_javascript(READ_AND_CLEAR_JS, timeout=5.0)
            await send(str(typed or ""))

        with ui.column().classes("ac-card w-full gap-3"):
            ui.label("Type your question here").classes("ac-h2")
            (
                ui.element("input")
                .props(
                    f"id={BOX_ID} type=text autocomplete=off "
                    'aria-label="Your question" '
                    'placeholder="For example: What is my water pill for?" '
                    f"maxlength={MAX_QUESTION_CHARS}"
                )
                .style(BOX_STYLE)
                .on("keydown.enter", send_typed)
            )
            button("Ask", on_click=send_typed)

        ui.label("Not sure what to ask? Try one of these.").classes("ac-small")
        with ui.row().classes("w-full gap-2"):
            for example in ASK_EXAMPLES:
                button(
                    example,
                    kind="soft",
                    arrow=False,
                    on_click=lambda asked=example: send(asked),
                )
        button("Home", kind="ghost", href="/")
