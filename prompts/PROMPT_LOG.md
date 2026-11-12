# Prompt log

One entry per prompt version. Newest at the top. See the `aftercare-prompt-change` skill for the procedure.

| Version | Date | Author | The one change | Why | Before → after (eval) | Kept? |
|---------|------|--------|----------------|-----|-----------------------|-------|
| extraction v1 | 2026-11-11 | Nikhil | New prompt: copy a discharge document into the structured profile, with an exact source quote per item | Upload pipeline (ADR-0035) needs a transcriber that never interprets | No baseline (new). Verified so far with a fake model only; record the first real run on the Patient 1 PDF here (expect 6 medicines, amlodipine STOPPED, acetaminophen AS_NEEDED) | Pending real run |
| answer v7 | 2026-10 | Team | Final answer-agent prompt from the v1–v7 design iterations | Baseline for the build | Record the first full run of `tests/eval/run_eval.py` here | Yes (baseline) |
