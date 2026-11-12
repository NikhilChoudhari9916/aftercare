# ADR-0040: The summary, schedule and calendar are built by plain code from the confirmed profile

- **Status:** Accepted
- **Date:** 2026-11-12
- **Deciders:** team
- **Supersedes:** none (applies ADR-0006 and CLAUDE.md section 4: "the summary and schedule screens are built directly from the profile, without agents")

## Context

After the patient confirms the extracted items, three screens come next: a plain-language summary, a medicine schedule, and a calendar file for reminders. A wrong time or a wrong dose here is a safety problem, and a model that "helpfully" fills gaps is exactly the risk.

## Decision

All three are produced by deterministic code in `app/summary/`, reading only items the patient confirmed.

- **Summary:** a template, not a model. Every sentence starts from the papers ("Your papers say…", "Your papers list…") and carries its page number, so the screen can show a "From your papers, page N" tag. It repeats the papers; it never says whether the patient has a condition and never tells anyone to start, stop, skip or change a medicine. A test checks the reading level (grade 7 or lower) and bans diagnosis and dose-advice wording.
- **Schedule:** a time of day is worked out only from words the papers use ("twice a day", "in the morning", "at bedtime"). Anything unclear ("every 6 hours", "once daily" with no time of day, "every other day", contradictory wording) is **shown as written** and the patient is asked to set the timing. STOPPED and AS NEEDED medicines never get a time. Words like "as needed" win even when the status field disagrees.
- **Times of day** use fixed everyday defaults (morning 8:00, midday 13:00, evening 18:00, bedtime 21:00). They are suggestions that are easy to move in the calendar app.
- **Calendar (.ics):**
  - Times are **floating** (no time zone is written), so each phone shows them in its own local time.
  - Titles are private by default ("Evening medicines", "Medical appointment"); `?titles=detailed` names the medicines.
  - Daily reminders cover **the next 30 days from today** (or from the discharge date if it is still ahead), and stop at a medicine's end date. Medicines with different end dates get separate events. Courses already over make no event.
  - Follow-ups become one-time events only when the papers write a full date; a clock time needs a.m. or p.m., otherwise the entry is all-day. "Within 7 days" stays text on the schedule page.
  - Event IDs are stable hashes (no patient ID inside) and `SEQUENCE` is the profile version, so importing a newer file updates the old events. The UI tells the patient to download again after the profile changes.
- **Access:** the owner and an aide may read all three (ADR-0032). Nothing is built until a version is confirmed (404 before that).

## Alternatives considered

- **Let the model write the summary:** more fluent, but it can add facts, drop a caution, or sound like a diagnosis. The validators and prompt work for model answers belong to the Q&A path; this screen does not need them.
- **Guess a time for unclear frequencies:** friendlier, but a guessed reminder for "every 6 hours" could be wrong in a way that matters. Asking is safer.
- **Anchor the 30 days to the discharge date:** matches the 30-day window literally, but reminders would already be over for anyone opening the app late, which is what happens in a demo.

## Consequences

- New package `app/summary/` (profile loader, summary, schedule, calendar export, routes) and two pinned dependencies: `icalendar` for the file and `textstat` for the reading-level check.
- The question graph's schedule tool (`get_schedule`) will call the same `build_schedule`, so answers and screens cannot disagree.
- Reminder times are not yet per-patient preferences; a `Preference` table can add that later without changing the schedule rules.
