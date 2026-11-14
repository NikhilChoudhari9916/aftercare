# ADR-0043: How the retriever is built, and the embedding model as an optional install

- **Status:** Accepted
- **Date:** 2026-11-13
- **Deciders:** team
- **Supersedes:** none (fills in ADR-0028; the design there is unchanged)

## Context

ADR-0028 chose per-patient hybrid search. Building it needed several choices it left open: how to cut the papers into chunks, how to score keywords on a corpus of about 15 chunks, which embedding model to use, and how to keep a model as heavy as PyTorch out of everyone's setup and out of CI.

## Decision

- **Chunks are made right after the patient confirms** (`app/qa/index.py`) and replace the previous set, so a medicine the patient removed can never be found. A chunk is either a section of the papers or one confirmed medicine.
  - **Sections:** plain page text has no font information, so a heading is a short line with a capital letter and some lowercase, no closing punctuation, followed by a full sentence. Sections over about 700 characters are cut between lines. Lines that repeat on every page (the hospital header, which holds the patient's name, record number and date of birth) are dropped, so they never reach search results or the model.
  - **Medicine rows** come from the *confirmed profile* and not from the page text, so a removed medicine has no row. The papers' own table text also stays searchable as a section, because it holds sentences that are not in any row (for example the ibuprofen warning). A medicine the patient removed can therefore still be named in that raw text; the papers are the patient's own document, and confirmation applies to the facts we extract from them.
- **Keywords:** BM25 (`rank-bm25`, Okapi). "Shares a word with the question" is checked directly rather than by score, because Okapi scores a word found in every document as zero or negative, which made a patient with one short chunk unsearchable. Filler words are removed and a plural "s" is dropped.
- **Other names:** a question that names a confirmed medicine also searches its other names from the confirmed profile (`app/qa/aliases.py`). Names only; nicknames such as "water pill" are used only if they are in the profile.
- **Meaning:** `sentence-transformers/all-MiniLM-L6-v2` (small, English, runs on this machine). Vectors live in a FAISS index per patient under `storage/patients/{id}/index/`, are rebuilt whenever the patient's chunks change, and are deleted with the patient. The two ranked lists are merged by reciprocal rank fusion.
- **Embeddings are on by default** (`embeddings_enabled`, built by `build_retriever` in `app/qa/factory.py`) and fall back to keywords by themselves when the model is not installed.
- **Embeddings are an optional install.** `faiss-cpu` and `numpy` are in `requirements.txt` (small); `sentence-transformers`, which pulls in PyTorch, is in `requirements-embeddings.txt`. Without it, search runs on keywords only and `Retriever.last_mode` says so, which is the fallback ADR-0028 asks for. CI and unit tests use a fake embedder and never download a model.
- **No keyword-score threshold; the similarity threshold is 0.3.** On the 22 retrieval cases a keyword-score cutoff cannot separate good from bad hits: the weakest correct hit scored 0.64 and a wrong one scored 2.68, so the keyword rule stays "returns only passages that share a word". For embeddings, `embedding_min_similarity` in `app/config.py` is 0.3, chosen from a sweep (see Consequences).

## Alternatives considered

- **BM25Plus:** no negative-score problem, but it gives non-matching chunks a base score anyway, so the explicit shared-word check is still needed. It scored 14 of 22 against 16 of 22 for Okapi, which is a two-case gap on one small set and **not** evidence that Okapi is better; Okapi was kept because the shared-word check already fixes its problem.
- **A nickname dictionary ("water pill" means diuretic):** would raise the keyword score, but it hides exactly the gap embeddings are meant to close, and a hand-made list is a medical claim nobody reviewed.
- **Always install the embedding model:** simplest, but it adds a very large install for every teammate and a slow CI run for a feature unit tests do not need.
- **Build the index inside the confirm request:** the first model load takes seconds. The index is built on the first question instead, then reused.

## Consequences

- **Measured 2026-11-13** on the 22 retrieval cases that expect a source (right source in the top 4): keywords only **16 of 22 (73%)**, keywords plus meaning **20 of 22 (91%)**. Neither reaches the 95% target yet. The two remaining misses (A4 "is my water pill the same as before" and N2) are Patient 1 "water pill" questions where the right chunk ranks below label chunks about other medicines.
- **Measured over the chunks the app really makes** (`python -m tests.eval.retrieval_chunks [--embeddings]`, Patient 1, the answer's own words must appear in the top 4): keywords **23 of 26**, keywords plus meaning **23 of 26**. So embeddings are **not yet shown to help on real chunks**. Why this number is softer than the first one: the 20 direct questions are easy (one big table chunk holds several answers, and "water pill" matches by accident through "glass of water" in the potassium row). On the six paraphrase questions, meaning search fixed one ("my diuretic") that keywords missed, and merging cost one exact hit (the alcohol question) that keywords had, because weaker meaning-matches outranked it. Questions and phrases were written by the author of the retriever and the same set chose the scorer and threshold, so a held-out set from a teammate is still needed.
- **Similarity threshold:** a sweep from 0.2 to 0.55 (hits out of 22): 18, **20 at 0.3**, 19, 17, 16, 16, 16. No value separates the two "not in your papers" cases (T9, P2-T6) from real hits without losing real hits, so 0.3 stays and deciding that something is not covered is left to the answer agent and the validators, which the end-to-end eval measures.
- The question workflow reads `Retriever.last_mode` and records it in `QALog` (no patient text).
- Sections are not yet filtered by task (ADR-0028 mentions this); with about 15 chunks per patient it has not been needed.
- A teammate who wants the embedding search runs `pip install -r requirements-embeddings.txt` (see `TEAM_SETUP.md`). The first run downloads the model, about 90 MB, from Hugging Face.
