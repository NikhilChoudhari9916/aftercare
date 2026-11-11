import logging
import threading

import pytest
from sqlmodel import Session, select

from app.config import Settings
from app.jobs.extraction import run_extraction_job
from app.jobs.messages import friendly_error
from app.jobs.runner import InlineJobRunner, ThreadJobRunner, mark_interrupted_jobs
from app.models import (
    Document,
    Job,
    JobStatus,
    JobType,
    Patient,
    ProfileItem,
    ProfileVersion,
    User,
)
from app.storage import save_pdf
from tests.fakes import FakeLLM
from tests.samples import PATIENT1_PDF, patient1_profile


@pytest.fixture
def queued(db: Session, tmp_path) -> tuple[Job, Settings]:
    """A queued extraction job for a stored copy of the Patient 1 PDF."""
    user = User(google_sub="s", email="a@example.com", display_name="A")
    db.add(user)
    db.flush()
    patient = Patient(owner_user_id=user.id)
    db.add(patient)
    db.flush()
    document = Document(patient_id=patient.id, page_count=3)
    db.add(document)
    db.flush()
    settings = Settings(storage_dir=tmp_path)
    save_pdf(settings.storage_dir, patient.id, document.id, PATIENT1_PDF.read_bytes())
    job = Job(patient_id=patient.id, document_id=document.id, type=JobType.EXTRACT)
    db.add(job)
    db.commit()
    return job, settings


def run(db: Session, job: Job, llm: FakeLLM, settings: Settings) -> Job:
    run_extraction_job(
        job.id, session_factory=lambda: Session(db.get_bind()), llm=llm, settings=settings
    )
    db.expire_all()
    return db.get(Job, job.id)


def test_the_inline_runner_runs_the_work_immediately():
    ran = []
    InlineJobRunner().submit(lambda: ran.append(1))
    assert ran == [1]


def test_the_thread_runner_runs_work_in_a_worker_thread():
    done = threading.Event()
    where = []
    runner = ThreadJobRunner(max_workers=1)

    def work() -> None:
        where.append(threading.current_thread().name)
        done.set()

    runner.submit(work)
    assert done.wait(timeout=5)
    runner.shutdown()
    assert where[0].startswith("job")
    assert where[0] != threading.current_thread().name


def test_after_a_restart_queued_and_running_jobs_are_marked_interrupted(db: Session, queued):
    job, _ = queued
    running = Job(patient_id=job.patient_id, type=JobType.EXTRACT, status=JobStatus.RUNNING)
    finished = Job(patient_id=job.patient_id, type=JobType.EXTRACT, status=JobStatus.SUCCEEDED)
    db.add_all([running, finished])
    db.commit()

    assert mark_interrupted_jobs(db) == 2

    db.expire_all()
    assert db.get(Job, job.id).status == JobStatus.FAILED
    assert db.get(Job, job.id).error_code == "interrupted"
    assert db.get(Job, running.id).status == JobStatus.FAILED
    assert db.get(Job, finished.id).status == JobStatus.SUCCEEDED


def test_a_successful_job_stores_pages_a_draft_profile_and_its_items(db: Session, queued):
    job, settings = queued
    llm = FakeLLM(extractions=[patient1_profile()])

    done = run(db, job, llm, settings)

    assert (done.status, done.step, done.error_code) == (JobStatus.SUCCEEDED, "done", None)
    assert done.started_at is not None and done.finished_at is not None
    version = db.exec(select(ProfileVersion)).one()
    assert (version.version, version.status, version.discharge_date) == (1, "DRAFT", "2026-10-12")
    assert len(db.exec(select(ProfileItem)).all()) == 11


def test_a_quote_that_never_verifies_is_stored_as_not_found(db: Session, queued):
    job, settings = queued
    bad = patient1_profile()
    medicines = list(bad.medicines)
    medicines[0] = medicines[0].model_copy(update={"source_quote": "Take purple pills at dawn."})
    bad = bad.model_copy(update={"medicines": medicines})
    llm = FakeLLM(extractions=[bad, bad])

    run(db, job, llm, settings)

    statuses = {
        (item.section, item.position): item.quote_status
        for item in db.exec(select(ProfileItem)).all()
    }
    assert statuses[("medicines", 0)] == "not_found"
    assert statuses[("medicines", 1)] == "verified"


def test_a_crash_fails_the_job_and_the_log_never_contains_the_message(
    db: Session, queued, caplog: pytest.LogCaptureFixture
):
    job, settings = queued
    llm = FakeLLM(extractions=[RuntimeError("secret patient text: metoprolol 25 mg")])

    with caplog.at_level(logging.ERROR):
        done = run(db, job, llm, settings)

    assert (done.status, done.error_code) == (JobStatus.FAILED, "internal_error")
    assert "RuntimeError" in caplog.text
    assert "metoprolol" not in caplog.text
    assert db.exec(select(ProfileVersion)).first() is None


def test_a_job_that_no_longer_exists_is_ignored(db: Session, queued):
    _, settings = queued
    run_extraction_job(
        "no-such-job",
        session_factory=lambda: Session(db.get_bind()),
        llm=FakeLLM(),
        settings=settings,
    )


@pytest.mark.parametrize(
    "code",
    [
        "not_a_pdf",
        "no_text_layer",
        "ai_unavailable",
        "ai_refused",
        "extraction_failed",
        "interrupted",
    ],
)
def test_every_error_code_has_a_plain_sentence(code):
    assert friendly_error(code).endswith(".")


def test_unknown_error_codes_get_the_generic_sentence_and_none_gives_none():
    assert friendly_error("surprise") == friendly_error("internal_error")
    assert friendly_error(None) is None
