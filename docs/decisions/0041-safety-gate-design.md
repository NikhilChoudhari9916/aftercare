# ADR-0041: How the safety gate is built

- **Status:** Accepted
- **Date:** 2026-11-12
- **Deciders:** team
- **Supersedes:** none (fills in the details of ADR-0005)

## Context

ADR-0005 fixed the shape of the gate: three tiers, keyword rules plus a small classifier run three times, the more severe result wins, a classifier failure means Tier 2. Building it needed a handful of smaller choices, and some of them change what a patient sees. They are recorded here so the team can review them.

## Decision

- **Code:** `app/safety/` (`messages.py`, `rules.py`, `classifier.py`, `gate.py`, `context.py`) and `data/red_flags.yaml`. The gate takes a plain `PatientSafetyContext` (confirmed warning signs, medicine names, care team contact), never the profile object, so nothing in the safety path can change patient data.
- **Rules only raise the tier.** They read the YAML file plus the patient's own confirmed warning signs and medicine names. A broken or missing rules file stops the app with an error instead of loading partial rules.
- **Tier 1 stops early.** If the rules say Tier 1, the gate returns the fixed 911 text and does not call the model at all. Nothing the classifier said could lower the tier, so the call would only add cost and delay.
- **Any classifier problem counts as Tier 2, per run.** A run that errors, times out (10 seconds for all three together, in `app/config.py`), or answers in a way we cannot read counts as Tier 2. One failed run is enough to raise a Tier 3 question to Tier 2. This is deliberately cautious: it favors a needless "call your care team" over a missed problem, and it means a flaky API shows up as extra Tier 2 answers, which the logs can count.
- **Unreadable replies are read conservatively.** If a reply names several tiers, the most serious one counts.
- **The classifier sees the patient's own warning signs** as data, plus its own prompt (`prompts/safety_classifier_system_prompt_v1.txt`), and the question is wrapped so it cannot close its own tag. Because the final tier is the more severe of rules and classifier, text in a question that tries to talk the classifier down cannot lower a tier the rules already set.
- **"Stop" is not a rule word.** "When do I stop the Xarelto?" is a plain question about the papers. Skipping, doubling, forgetting or missing a dose next to one of the patient's medicine names is Tier 2 by rule; whether stopping early is a Tier 2 matter is left to the classifier.
- **Matching the patient's own warning signs is approximate.** A sign is split into parts and a part matches when most of its key words (lightly stemmed, ignoring numbers and filler) appear in the question. A part that is only a vague word such as "pain" is ignored. The classifier sees the same signs, so a sign the word-matching misses can still be caught.
- **The result holds no patient text:** the tier, which rules matched (by name), what each classifier run said, how many failed, and the fixed reply for Tier 1.

## Alternatives considered

- **Call the classifier even when the rules say Tier 1:** the result could not change, so only cost and delay.
- **Ignore failed runs when others succeeded:** friendlier during an outage, but one failed run might be the one that would have seen the emergency.
- **Regular expressions for stopping a medicine:** tried in thought, rejected: too many plain questions would be sent to the care team.
- **Embedding or fuzzy matching for the patient's warning signs:** more recall, but a new dependency and harder to audit. The classifier covers the gap.

## Consequences

- Tier 1 recall by rules alone is 100% on the 31 eval questions, and `tests/safety/test_eval_cases.py` fails if that changes. The rules also leave all 18 everyday questions unescalated.
- Real-model behavior was measured on 2026-11-12 (claude-haiku-5-5, 31 eval questions, 3 repeats): Tier 1 recall 4/4, every Tier 2 case exactly Tier 2, and 20 of 21 everyday questions kept at Tier 3. The one over-escalation is P3-L1 (a patient says the hospital stopped lisinopril, with conflicting paperwork); it is logged in `prompts/PROMPT_LOG.md` for the team to decide. The first run showed that a 20-token reply limit sometimes cut off a one-line answer and the run was discarded as a failure, so the limit is 200 tokens. This was a one-off script, not the permanent eval runner (handoff item C2), which should repeat the measurement on every prompt or model change.
- The question workflow (B5) calls `run_gate` first, uses `fixed_reply` for Tier 1, and uses `care_team_line` from `messages.py` to lead Tier 2 answers.
- Three calls per question mean the classifier runs in parallel threads; endpoints should call `run_gate` from a worker thread, not directly in an `async` function.
- Suggested additions for the team to review (not built, because CLAUDE.md names the emergency kinds and a change needs a decision): allergic-reaction signs (swelling of the lips or throat), chest-pain-adjacent wording in other languages.
