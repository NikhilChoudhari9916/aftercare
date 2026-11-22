# Challenges, fixes and remaining limits

Verified locally, 2026-11-21; not a statement that these changes are merged into main.

| Challenge observed | Response implemented | Evidence / remaining limit |
|---|---|---|
| Supported list questions could return a generic pharmacist fallback | Two common list intents use typed original-row lookup and fixed answers, bypassing generated prose | Both questions passed through the live API and browser. Unknown/incomplete table layouts still use the ordinary path |
| Table columns interleave names, instructions and status markers in extracted text | Retain complete rows and their warnings; count status markers before enumerating a complete list | Tests use the actual PDF reader's sorted text, not an invented flat sample |
| Citation existence does not prove a model's interpretation | Release original excerpts and verified-row templates; discard generated medical interpretations | Deliberately wrong reviewer approvals cannot release the invented sleep claim |
| Profile edits used to replace the original value without history | Separate immutable original pages, extraction values and user edits | Comparisons appear in Review/Summary/Schedule/Ask; disputed values are withheld |
| “It” can refer to several medicines | Resolve only from explicit recent user context; clarify if no identity is available | Executed two-turn example and offline ambiguity tests; memory does not supply medical facts |
| Live testing can cost money | Offline suite first; a small live sample with a thread-safe $0.75 reservation cap | 32 live calls, estimated $0.089158; not a 33-case repeated prompt benchmark |

## Limits to state in the submission

- Synthetic data only; this is a course prototype, not clinically validated care.
- UI testing used the real freshly extracted data and a free scripted safety classifier. The
  separate seven-question API check used the configured real models. Do not call these five
  external-user tests or imply that browser screenshots are a live-model benchmark.
- Tools are MCP-style typed interfaces in-process. There is no standalone MCP protocol server.
- Session memory is bounded and short term. Long-term patient logs and visit prep are deferred.
- Local development login was used. This is not a production authentication/deployment review.
- Purpose matching is deliberately limited. Missing purposes are not supplied from model
  knowledge; the sample medicine list explicitly supports a pain use for acetaminophen, not
  a purpose for every medicine.
- A single unresolved edit currently pauses all Ask answers and calendar downloads. Old edit
  history cannot be reconstructed. These conservative restrictions need later usability work.
- The 30-second agent limit is checked between steps. A provider call has its own timeout and
  SDK retries, so it can exceed that elapsed time. A strict cancellation mechanism is future work.
- Original excerpts can be longer than the old generated-answer target. Retrieval can miss a
  passage; digital text extraction and quoted context still require evaluation against the PDF.
- Fixed sample appointments are in October 2026; do not silently move them to future dates.
