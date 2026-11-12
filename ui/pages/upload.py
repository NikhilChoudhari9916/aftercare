from fastapi import Request
from nicegui import events, ui

from ui.api_client import BackendUnavailable, JobInfo, NotSignedIn, Rejected
from ui.content import job_step_text
from ui.layout import (
    backend,
    footer,
    heading,
    link_button,
    page_column,
    session_token,
    signed_in_owner,
)

MAX_PDF_BYTES = 10 * 1024 * 1024
POLL_SECONDS = 1.5


@ui.page("/upload")
async def upload_page(request: Request) -> None:
    found = await signed_in_owner(request)
    if found is None:
        return
    _, patient = found
    token = session_token(request)
    job_id: str | None = None

    async def start(event: events.UploadEventArguments) -> None:
        nonlocal job_id
        uploader.set_visibility(False)
        message.set_text("")
        try:
            result = await backend.upload_document(
                token, patient.id, event.file.name, await event.file.read()
            )
        except Rejected as error:
            fail(str(error))
        except NotSignedIn:
            ui.navigate.to("/")
        except BackendUnavailable:
            fail("AfterCare can't reach its server right now. Please try again in a moment.")
        else:
            job_id = result.job_id
            progress.set_visibility(True)
            step.set_text("Waiting to start")
            poller.activate()

    async def poll() -> None:
        try:
            job = await backend.get_job(token, job_id or "")
        except NotSignedIn:
            ui.navigate.to("/")
            return
        except BackendUnavailable:
            return  # a missed check is not a failure; the next one tries again
        show(job)

    def show(job: JobInfo) -> None:
        if job.status == "SUCCEEDED":
            poller.deactivate()
            ui.navigate.to("/confirm")
        elif job.status == "FAILED":
            poller.deactivate()
            fail(job.message or "Something went wrong. Please try again.")
        else:
            step.set_text(job_step_text(job.status, job.step))

    def fail(text: str) -> None:
        progress.set_visibility(False)
        message.set_text(text)
        uploader.reset()
        uploader.set_visibility(True)

    def too_big(_: events.UiEventArguments) -> None:
        message.set_text("That file is too large. Please choose a PDF under 10 MB.")

    with page_column():
        heading("Upload your discharge papers")
        ui.label(
            "Choose the PDF you were given when you left the hospital. "
            "It must be a digital PDF, not a photo or a scan."
        ).classes("text-lg")
        message = ui.label().classes("text-negative text-base").props('role="alert"')
        uploader = (
            ui.upload(
                on_upload=start,
                on_rejected=too_big,
                auto_upload=True,
                max_files=1,
                max_file_size=MAX_PDF_BYTES,
                label="Choose your PDF",
            )
            .props('accept=".pdf,application/pdf" flat bordered')
            .classes("w-full")
        )
        with ui.row().classes("items-center gap-3") as progress:
            ui.spinner(size="lg")
            step = ui.label().classes("text-lg").props('role="status"')
        progress.set_visibility(False)
        poller = ui.timer(POLL_SECONDS, poll, active=False)
        link_button("Back", "/", outline=True)
        footer()
