# Sources: data and AI tools

License or terms text is given **only where the repository already says it**. Where it does not, the
entry says UNVERIFIED. Nothing here was looked up online.

## (a) Data used or referenced in this repository

| Source | How it is used | Where | License or terms, as written in this repo |
|---|---|---|---|
| Synthetic patients (3) | Test and demo patients: one discharge PDF (Patient 1), and text profiles and source files for Patients 1 to 3 | `data/synthetic/` (`patient1_discharge_summary.pdf`, `patient{1,2,3}_profile.txt`, `patient{1,2,3}_sources.txt`) | Written by the team; each profile starts "SYNTHETIC TEST PATIENT (no real patient data)" (`patient1_profile.txt:1`, `patient2_profile.txt:1`). No license file for them: UNVERIFIED |
| Eval cases | 33 questions with expected action, required facts and forbidden patterns | `tests/eval/eval_cases.json` (counted with `len(json.load(...)["cases"])`) | Team-written. The CLAUDE.md note ties one case to "HW2 case C7"; the HW2 material itself is not in this repository: UNVERIFIED |
| Retrieval cases | Which source IDs each eval question should retrieve | `tests/eval/retrieval_cases.json` | Team-written; no license text |
| openFDA drug labels | At runtime, the purpose and warnings sections for confirmed medicines only, through the `search_fda_label` tool (ADR-0027). In the eval, **synthetic stand-ins** replace live labels (`tests/eval/full_path.py:86-97`) | `app/enrichment/openfda.py`, `app/tools/label_tools.py`, base URL `app/config.py` (`openfda_base_url`) | "openFDA is public domain (CC0)" (`docs/decisions/0031-privacy-and-data-handling.md:19`). That is the repository's own statement; the official terms were not checked: UNVERIFIED |
| RxNorm (NLM RxNav) | Medicine names to IDs and other names, through `lookup_rxnorm` and the alias step. **Off in the eval run** (`tests/eval/full_path.py:13`) | `app/enrichment/rxnorm.py`, base URL `app/config.py` (`rxnav_base_url`) | No license or terms text in the repo: UNVERIFIED |
| MedlinePlus | **Decided but not built.** ADR-0023 chooses it for plain-language term definitions. There is no `medlineplus.py`, and no code calls it | `docs/decisions/0023-medlineplus-for-terms.md` | "MedlinePlus health-topic summaries are public domain and are credited 'Source: MedlinePlus, National Library of Medicine'. MedlinePlus drug pages are ASHP-copyrighted and are never ingested" (`0031-privacy-and-data-handling.md:19`) |
| Inter typeface | The web font | `ui/static/fonts/InterVariable.woff2` | SIL Open Font License 1.1 (`THIRD_PARTY_NOTICES.md:47-52`, licence file `ui/static/fonts/Inter-LICENSE.txt`) |
| Imported Claude Code skills (8) | Reference material for the team, not part of the app | `.claude/skills/` | MIT, from `Jeffallan/claude-skills` (`THIRD_PARTY_NOTICES.md`, ADR-0026) |
| Google sign-in | Identity only (`openid`, `email`, `profile`). **The demo uses the development test login instead** (ADR-0037) | `app/auth/google.py`, `app/auth/routes.py:142` | Not a data set; terms not stated in the repo |

Packages are pinned in `requirements.txt` (for example `anthropic==2.8.0`, `langgraph==1.2.20`,
`nicegui==3.18.0`). Their licenses are not recorded in the repository: UNVERIFIED.

## (b) AI tools

**Models the application uses at run time** (read from `app/config.py:35-37`; the IDs live only there):

| Role | Model ID | Used for |
|---|---|---|
| Main (`model_main`) | `claude-sonnet-5-5` | PDF extraction and the medication agent's answers |
| Fast (`model_fast`) | `claude-haiku-5-5` | The question router and the safety classifier (3 runs) |
| Strong (`model_strong`) | `claude-opus-5-5` | Configured, but a search of `app/` and `ui/` finds `model_strong` only in `config.py`, so nothing calls it. ADR-0018 allows it only for a task where Sonnet falls short |

The embedding model for search is local and open source: `sentence-transformers/all-MiniLM-L6-v2`
(`app/config.py`, `embedding_model`). It is optional (`requirements-embeddings.txt`), and search falls
back to keywords without it.

**AI tools used to build this project: TO CONFIRM BY TEAM (Claude, Claude Code ...)**

The repository does record that the team uses Claude Code (`.claude/`, `CLAUDE.md`, ADR-0016) and
that some files were "drafted with Claude" (`prompts/PROMPT_LOG.md`). The exact tools, versions and
what each was used for are for the team to fill in; this file does not guess.
