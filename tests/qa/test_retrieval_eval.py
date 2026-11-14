from tests.eval.retrieval import report, run

# Measured 2026-11-13 with keyword search only: 16 of 22. The target is 95% (CLAUDE.md section 8),
# which keyword search cannot reach alone: it cannot link "water pill" to furosemide when the
# papers never say so. This floor stops a change from quietly making it worse.
BM25_FLOOR = 16


def test_keyword_search_keeps_finding_the_right_source_in_the_top_four():
    results = run()
    found = sum(r.passed for r in results if not r.expects_nothing)

    assert found >= BM25_FLOOR, report(results)


def test_every_expected_source_exists_in_its_patients_sources():
    import json

    from tests.eval.retrieval import CASES_FILE, load_sources

    data = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    for case in data["cases"]:
        ids, _ = load_sources(data["patients"][case["patient"]]["sources"])
        assert set(case["expected"]) <= set(ids), case["id"]
