from fastapi import Request
from nicegui import events, ui

from ui.api_client import BackendUnavailable, JobInfo, NotSignedIn, Rejected
from ui.backend import backend, session_token
from ui.components.basics import alert, button, tip
from ui.components.shell import app_shell
from ui.components.steps import StepTracker
from ui.layout import signed_in_owner

MAX_PDF_BYTES = 10 * 1024 * 1024
POLL_SECONDS = 1.5


@ui.page("/upload")
async def upload_page(request: Request) -> None:
    found = await signed_in_owner(request)
    if found is None:
        return
    me, patient = found
    token = session_token(request)
    job_id: str | None = None

    async def start(event: events.UploadEventArguments) -> None:
        nonlocal job_id
        form.set_visibility(False)
        message.set_visibility(False)
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
            tracker.update("QUEUED", None)
            progress.set_visibility(True)
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
        tracker.update(job.status, job.step)
        if job.status == "SUCCEEDED":
            poller.deactivate()
            ui.navigate.to("/confirm")
        elif job.status == "FAILED":
            poller.deactivate()
            fail(job.message or "Something went wrong. Please try again.")

    def fail(text: str) -> None:
        progress.set_visibility(False)
        message.set_text(text)
        message.set_visibility(True)
        uploader.reset()
        form.set_visibility(True)

    def too_big(_: events.UiEventArguments) -> None:
        message.set_text("That file is too large. Please choose a PDF under 10 MB.")
        message.set_visibility(True)

    with app_shell(me):
        with ui.column().classes("gap-1 fade-up"):
            ui.label("Upload your papers").classes("ac-title")
            ui.label("Choose the PDF you were given when you left the hospital.").classes("ac-lead")

        with ui.column().classes("w-full gap-4 fade-up") as form:
            message = alert("")
            message.set_visibility(False)
            uploader = (
                ui.upload(
                    on_upload=start,
                    on_rejected=too_big,
                    auto_upload=True,
                    max_files=1,
                    max_file_size=MAX_PDF_BYTES,
                    label="Tap to choose your PDF",
                )
                .props('accept=".pdf,application/pdf" flat')
                .classes("ac-drop")
            )
            tip("Digital PDFs only for now, not photos or scans. Files up to 10 MB.")

        with ui.column().classes("ac-card fade-up") as progress:
            ui.label("Reading your papers").classes("ac-h2")
            tracker = StepTracker()
            ui.label("This usually takes less than a minute.").classes("ac-small")
        progress.set_visibility(False)

        poller = ui.timer(POLL_SECONDS, poll, active=False)
        button("Back", kind="ghost", href="/")
