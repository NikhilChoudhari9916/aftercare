# Assignment 4 demo and submission checks

Use `data/synthetic/patient1_discharge_summary.pdf` only. Do not add real patient data.

## Demonstrate the three core use cases

1. Start the backend and UI in two terminals from this checkout (activate `.venv` in each).
   Use the same DATABASE_URL and STORAGE_DIR as the existing session if resuming an upload.
   Backend: `APP_ENV=development DEV_LOGIN=1 python -m uvicorn app.main:app --port 8000`.
   UI: `APP_ENV=development DEV_LOGIN=1 python -m ui.main`.
2. Sign in with the synthetic development account. Explain that it is development login.
3. Upload the sample PDF, review every item against its source, and confirm unchanged items.
   Show Summary. In the recorded live extraction there were six medicines and three follow-ups.
4. Open Ask. Ask “Which medicine is new?” and show metoprolol and potassium chloride with page 1
   citations. Ask “What is each of my medicines for?” and explain the explicit pain-use quote and
   the entries whose purposes cannot be verified. Do not claim the system fills those gaps.
5. Ask “What is furosemide also called?” then “When do my papers say to take it?” to show session
   reference resolution with original evidence. Ask the latter first in a fresh session to show
   clarification rather than guessing.
6. Show Schedule and the calendar download. Distinguish reminder choices from the paper's facts.
7. Optional safety branch: type “My chest hurts badly” (a synthetic software test) and show the
   fixed 911 message. Never click the telephone link during the classroom demo.

Changing a confirmed item intentionally creates a review discrepancy and blocks Ask/calendar;
use a separate synthetic upload to demonstrate that branch, not the main unchanged demo profile.
Restart both services after code changes so an older in-memory module cannot keep serving replies.

## Reproduce the offline checks

`APP_ENV=test ANTHROPIC_API_KEY='' python -m pytest -m 'not eval' -q`

`ruff check .` and `ruff format --check .`

The live sample and the per-case outputs are retained in `live-evidence.json`. Prices and token
usage are estimates, not an account billing statement. Full prompt stability testing is separate.

## Submission

Review the five-slide deck and its notes against the six rubric rows in README.md. Demonstrate
only the workflows actually shown here. Confirm names, citations and remaining limits yourself,
then upload the slides to the course portal; this task does not submit anything to Canvas.
