# ADR-0048: The FDA label answers a plain "what is it for?" question the papers do not

- **Status:** Accepted by the project owner's request, 2026-11-26. Teammate review is still needed.
- **Supersedes in part:** ADR-0046, only where it says the FDA label is never evidence.
  Everything else in ADR-0046 and ADR-0047 stands.

## Context

ADR-0046 made Ask show only original excerpts of the patient's own papers. That is safe, but a
basic question such as "What does furosemide do?" now gets "I couldn't verify an answer in the
original document text" whenever the papers name a medicine without saying why it is taken. Our
original design (CLAUDE.md, ADR-0027) already planned the FDA label's "indications and usage"
as general information, with the papers winning. The tool for it exists and is tested, but Ask
had it switched off (`openfda=None`).

The risk ADR-0046 guards against is real: a model's paraphrase can state a purpose the papers
never gave, and a label lists several uses without saying which one is the patient's.

## Decision

- A plain purpose question about **one confirmed medicine** ("What does X do?", "What is X
  for?", "Why am I taking X?", and "What is it for?" right after a question that named X) is
  answered by a graph step written in plain code. The model writes none of the reply.
- **The papers win.** If the original medicine-list row states a purpose, that row is shown
  as original words, exactly as for the list questions in ADR-0047, and no lookup is made.
- Otherwise the step reads the label's **"indications and usage" only** (never dosage or
  warnings) for that confirmed medicine, through the existing read-only `search_fda_label`
  tool, which refuses any medicine that is not on the patient's confirmed list.
- The reply says the papers do not state a purpose, then shows the start of the label's words
  under "General information from the FDA drug label, in its own words", tagged "From the drug
  label". It then says the label may list several uses and does not say which one is the
  patient's, and sends the patient to their care team or pharmacist. It is never worded as the
  patient's own reason, and it never says the patient has a condition.
- The label's words are **not rewritten**. Only layout is removed: the section heading, its
  numbering, "( 1.1 )" cross-references and characters the page could read as markup. A long
  section is cut at a sentence end to about 450 characters, with an ellipsis.
- If the label cannot be fetched, has no usage section, or the service is down, the reply says
  so and sends the patient to a person. It never becomes an error page and never guesses.
- Only the medicine's name (generic and brand names from the confirmed profile) goes to
  openFDA. No patient text, question or identity is sent. Labels are cached for a week.
- Anything else still follows ADR-0046: other questions, other external services (RxNorm,
  MedlinePlus) and the model's own knowledge are not evidence.
- A new setting, `fda_label_lookup` (default on), switches the lookup off. Tests keep it off.

## Consequences

- Like the fixed list answers in ADR-0047, this reply is composed by code, so the output
  validators do not run on it. Its safety rests on the fixed wording, the confirmed-medicine
  limit, the verbatim label text and the tests.
- Label text is clinical language and can be hard to read. It is shown as written rather than
  rewritten, which keeps the paraphrase risk out. If that proves too hard for patients, the
  next step is a team decision, not a model rewrite.
- The lookup adds up to four short requests to an outside service on this one path, each with
  the 5-second limit in `external_timeout_seconds`. It has no hard total deadline of its own;
  that belongs to the cost and concurrency work (security review F6).
- A question that names no medicine ("What is my water pill for?") is unchanged, because
  matching a lay term to a medicine needs a mapping the team has not decided on.
- This does not establish clinical correctness, and a label's uses are general, not the
  patient's.
