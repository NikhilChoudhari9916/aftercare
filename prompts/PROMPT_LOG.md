# Prompt log

One entry per prompt version. Newest at the top. See the `aftercare-prompt-change` skill for the procedure.

| Version | Date | Author | The one change | Why | Before → after (eval) | Kept? |
|---------|------|--------|----------------|-----|-----------------------|-------|
| safety classifier v1 | 2026-11-12 | Nikhil | New prompt: read one patient message and answer TIER 1, TIER 2 or TIER 3 (run 3 times, most severe wins) | Safety gate (ADR-0005, ADR-0041) needs a model reading on top of the keyword rules | No baseline (new). Verified with a fake model only: tier parsing, 3 runs, a failed run counts as Tier 2, question wrapped, patient warning signs included. **Not yet run on the real model.** Run it over `tests/eval/eval_cases.json` (3 runs per case) and record Tier 1 recall (must be 100%) and any over-escalation of "Just answer" cases here | Pending real run |
| extraction v1 | 2026-11-11 | Nikhil | New prompt: copy a discharge document into the structured profile, with an exact source quote per item | Upload pipeline (ADR-0035) needs a transcriber that never interprets | No baseline (new). Verified so far with a fake model only; record the first real run on the Patient 1 PDF here (expect 6 medicines, amlodipine STOPPED, acetaminophen AS_NEEDED) | Pending real run |
| answer v7 | 2026-10 | Team | Final answer-agent prompt from the v1–v7 design iterations | Baseline for the build | Record the first full run of `tests/eval/run_eval.py` here | Yes (baseline) |
