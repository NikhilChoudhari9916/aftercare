from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from sqlmodel import Session, select

from app.models import Job, JobStatus, utc_now


class JobRunner(Protocol):
    def submit(self, work: Callable[[], None]) -> None: ...


class ThreadJobRunner:
    """A small in-process worker pool (ADR-0034). Jobs live only as long as the process."""

    def __init__(self, max_workers: int) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job")

    def submit(self, work: Callable[[], None]) -> None:
        self._pool.submit(work)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


class InlineJobRunner:
    """Runs the work right away. For tests, so they stay fast and deterministic."""

    def submit(self, work: Callable[[], None]) -> None:
        work()


def mark_interrupted_jobs(db: Session) -> int:
    """After a restart, work that was queued or running is gone. Say so instead of waiting."""
    jobs = db.exec(select(Job).where(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))).all()
    for job in jobs:
        job.status = JobStatus.FAILED
        job.error_code = "interrupted"
        job.finished_at = utc_now()
        db.add(job)
    db.commit()
    return len(jobs)
