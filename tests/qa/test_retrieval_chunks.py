from tests.eval.retrieval_chunks import report, run

# Measured 2026-11-13 over the chunks the app really makes for Patient 1: keywords 23 of 26 and
# keywords plus meaning 23 of 26. The 20 phrase-from-the-papers questions are easy: one big table
# chunk holds several answers, and "water pill" matches by accident through "glass of water".
# The six paraphrase questions (M1 to M6) are the honest test. This floor only stops a slide.
KEYWORD_FLOOR = 23


def test_keyword_search_keeps_finding_the_answer_in_the_chunks_the_app_makes():
    results = run()

    assert sum(r.passed for r in results) >= KEYWORD_FLOOR, report(results)
