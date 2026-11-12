# ADR-0042: The patient's own plan for reminder times and visits, kept apart from the papers

- **Status:** Accepted
- **Date:** 2026-11-12
- **Deciders:** team
- **Supersedes:** none (extends ADR-0007 and ADR-0040; the confirmation step itself stays)

## Context

The first confirmation screen treated everything alike: a "Looks right / Remove / Fix it" card with free-text boxes. Two kinds of item are not alike.

- **A medicine is verification, and a wrong dose is harmful.** The patient must check what the AI read against the paper line. *When* they take it is their own choice, not something the papers say.
- **A visit is planning.** The papers give a booked date and time, or only a window ("any time 7 a.m. to 4 p.m."), or only a to-do ("within 7 days, please call to schedule"). The patient has to choose or book something. A text box cannot do that, and guessing a time makes a wrong calendar entry (the first real extraction showed this).

## Decision

**Keep what the papers say and what the patient chooses in different places.** The papers' words and their source quotes are never changed by planning. The patient's choices are stored in two new tables, `MedicinePlan` and `VisitPlan`, tied to the confirmed items, and are shown as "your choice", never as "from your papers".

**Planning happens on the Schedule page, in one form, saved once.** The patient sets reminder times for all medicines at once and plans every visit, then taps one Save button. The owner can save; an aide can only read (ADR-0032).

- **Medicine times:**
  - Each medicine that has a schedule gets one or more times (a time picker), prefilled with the everyday defaults (8:00, 13:00, 18:00, 21:00) when the papers say when.
  - When the papers give a clear count ("twice a day") the patient must give exactly that many times. When they do not ("every 6 hours"), the patient chooses between 1 and 6 times. Nothing is guessed.
  - STOPPED and AS NEEDED medicines never get times.
  - The count and the allowed values are checked by code on the server.
- **Visits:** each visit is either **booked** (a date is required, a time is optional) or **not booked yet** (the patient may pick a day to be reminded to call).
  - The screen says plainly what the papers gave: a booked date and time to confirm, a window or date to choose a time for, or "you still need to call".
  - Dates and times are checked by code. The app never books anything and never contacts a clinic.
- **Reminders are calendar entries** in the downloaded `.ics` file ("Call to book: Primary care follow-up" on the chosen day, all day). The app does not send notifications, emails or messages.
- **No plan, no change.** Until the patient saves a plan, the schedule and calendar behave exactly as before (ADR-0040), using defaults and the papers' own dates.
- **The plan belongs to one confirmed version.** If the patient uploads and confirms new papers, the old plan no longer applies and they plan again. Its items have new IDs, and carrying choices across would risk attaching a time to the wrong medicine.
- **The confirm screen gets stricter for medicines:**
  - The dose and how often are shown in large tiles next to the paper's words. A missing one shows "Not found" in red (a stopped medicine's missing schedule is not a gap).
  - An item whose quote could not be found gets an outline, a "Check this one" label, and a count at the top of the screen.
  - Editing is framed as "This doesn't match my papers", with a warning to change something only if the papers say something different, and a "You changed this" label appears while a value differs from what was read.
  - The *choice* of when to take a medicine is no longer on this card. The papers' own timing words can still be corrected there (an AI misreading of the paper is a verification error), under a label that says so.
  - Visits are confirmed as words only; planning is the next step on the Schedule page, which the "confirmed" screen leads to.

## Alternatives considered

- **One time per time-of-day slot instead of per medicine:** simpler, but a medicine whose timing is unclear does not fit a slot, and two medicines with the same slot may need different times.
- **Choose times at confirmation:** mixes two tasks on one card, which is the problem we are fixing.
- **Push notifications or email reminders:** needs a messaging service, storage of contact details and consent. Out of scope; calendar apps already do this well.
- **An agent that books appointments:** out of scope. AfterCare explains and never acts for the patient (CLAUDE.md section 1).
- **Carry the plan over to new papers by medicine name:** possible later; wrong carry-over is worse than asking again.

## Consequences

- Two tables (`MedicinePlan`, `VisitPlan`), a plan loader, validation, and `PUT /patients/{id}/plan` (owner only). `GET /patients/{id}/schedule` also returns the chosen and suggested values (owner and aide). CLAUDE.md sections 9 and 11 are updated in the same PR.
- The schedule groups doses by their exact time, not by four fixed slots; the part-of-day label comes from the hour.
- Calendar event IDs now depend on the time, not the slot. Importing a file made before this change would add events instead of updating them; nothing is deployed yet.
- The question workflow's schedule tool can read the same schedule, so answers say "you chose 7:30 AM" only for the patient's choice and "your papers say once a day, in the morning" for the papers.
- Reminder times and the call-to-book date are health-related choices: they are patient data, are deleted with the patient, and are never written to logs (ADR-0031).
