# ADR-0034: Slow work runs as background jobs in an in-process runner

- **Status:** Accepted
- **Date:** 2026-11-01
- **Deciders:** team
- **Supersedes:** none

## Context

The upload pipeline calls the AI for extraction, then RxNorm, openFDA, and MedlinePlus, then builds embeddings and a search index. That takes far longer than a normal web request, so a browser waiting on the upload would time out. The team is three people building a course project, so the answer should stay small.

## Decision

- The backend runs slow work as **jobs** in a small **in-process runner**: a limited pool of workers started with the FastAPI app (2 at a time by default, set in `app/config.py`). No Celery, no Redis, no separate worker process.
- Every job has a row in a **`Job`** table: patient, type, status (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`), the current step name, a short **error code**, and timestamps. A job row never holds patient text, and failure messages shown to the user are written per error code, not copied from exceptions.
- `POST /documents` saves the PDF, creates the job, and returns **202** with the job ID straight away. `GET /jobs/{id}` returns the status and current step, and is limited to the patient's owner. The UI polls it every couple of seconds and shows progress.
- **Two jobs per document**, split at the human step: (1) *extract*: scan check, hidden-instruction scan, AI extraction, quote check, abbreviation cleanup, ending at "waiting for confirmation"; (2) *enrich and index*: starts when the patient confirms, and runs RxNorm, openFDA, MedlinePlus, chunking, and the per-patient index.
- **Restart safety:** at startup, any job still marked `RUNNING` is marked `FAILED` with the code `INTERRUPTED`. The user can retry; the whole job re-runs from the stored PDF. Steps must be safe to re-run.
- **Limits checked before a job exists:** maximum PDF size and page count (set in `app/config.py`), so a huge file is rejected immediately with a friendly message.
- **Scheduled work reuses the runner:** the daily 30-day cleanup and invite expiry (ADR-0029, ADR-0032) are jobs of their own type, run by a simple timer.
- SQLite runs in WAL mode with short transactions, so jobs and requests do not block each other.

## Alternatives considered

- **Do it inside the request** — times out, and one slow upload ties up the server.
- **Celery or RQ with Redis** — correct at scale, but two extra services to run and secure for a team of three.
- **A separate worker process on a database queue** — the next step up if one process proves too small.

## Consequences

- New table `Job`, new `app/jobs/` module, and `GET /jobs/{id}`; `POST /documents` now returns 202, not the result.
- Jobs die with the process; the restart rule above makes that safe rather than silent.
- If we ever run more than one backend process (for example in a hosted demo), jobs could run twice. That needs a new ADR to move to a real queue.
- Tests use a runner that runs jobs inline, so they stay fast and deterministic, plus one test of the restart rule.
