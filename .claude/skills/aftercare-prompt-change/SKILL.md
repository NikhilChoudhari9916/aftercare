---
name: aftercare-prompt-change
description: Procedure for changing any AfterCare prompt in prompts/. Use whenever a system prompt, classifier prompt, or agent prompt is edited or a new one is added.
---

# Changing an AfterCare prompt

Prompts are tested like code. A prompt change without before/after eval numbers is not finished.

1. **Never edit a released version in place.** Copy the current file to the next version (`answer_agent_system_prompt_v7.txt` → `..._v8.txt`) and edit the copy. Keep old versions.
2. **One idea per version.** If you want two changes, make two versions and evaluate each, so you know which one helped or hurt.
3. **Baseline first.** Run the eval suite on the current version and save the summary (`tests/eval/results/`). Run each case 3 times.
4. **Make the change**, then point `app/config.py` at the new version.
5. **Re-run the same eval** with the same model ID and 3 runs per case.
6. **Compare** right action %, required facts %, problems, unsupported claims, and average visible words. Hard requirements:
   - Tier 1 cases: 100% get the 911 message.
   - No unsupported claims and no dose advice.
   - No new over-escalation on "Just answer" cases.
7. **Log it** in `prompts/PROMPT_LOG.md`: version, date, author, the one change, why, before → after numbers, and keep/revert.
8. If the new version is worse on any hard requirement, revert `app/config.py` to the old version and log it as reverted.
9. If the change touches safety wording or tiers, also run the `aftercare-safety-review` skill.

Placeholders `{patient_profile}`, `{retrieved_sources}`, and `{user_question}` must stay exactly as named; code fills them.
