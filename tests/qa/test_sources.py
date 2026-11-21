from app.qa.sources import SourceBook


def passages(*ids: str) -> dict:
    return {
        "ok": True,
        "data": {
            "passages": [
                {"id": i, "page": 1, "section": "Medication changes", "text": f"text of {i}"}
                for i in ids
            ]
        },
    }


def label(medicine: str, *, found: bool = True) -> dict:
    return {
        "ok": True,
        "data": {
            "found": found,
            "medicine": medicine,
            "purpose": "Treats swelling." if found else None,
            "warnings": "Can cause low potassium." if found else None,
            "boxed_warning": None,
        },
    }


def test_passages_are_kept_by_their_id_with_where_they_came_from():
    book = SourceBook()
    result = passages("D1", "D2")

    assert book.add_tool_result("search_patient_document", result) == result
    assert book.texts == {"D1": "text of D1", "D2": "text of D2"}
    assert book.meta["D1"] == {"kind": "paper", "page": 1, "section": "Medication changes"}


def test_a_label_gets_an_id_and_the_same_medicine_keeps_it():
    book = SourceBook()

    first = book.add_tool_result("search_fda_label", label("furosemide"))
    again = book.add_tool_result("search_fda_label", label("Furosemide"))
    other = book.add_tool_result("search_fda_label", label("lisinopril"))

    assert first["data"]["id"] == "L1"
    assert again["data"]["id"] == "L1"
    assert other["data"]["id"] == "L2"
    assert book.texts["L1"] == "Treats swelling. Can cause low potassium."
    assert book.meta["L1"] == {"kind": "label", "page": None, "medicine": "furosemide"}


def test_a_label_that_was_not_found_gets_no_id_and_adds_no_source():
    book = SourceBook()

    result = book.add_tool_result("search_fda_label", label("nothing", found=False))

    assert "id" not in result["data"]
    assert book.texts == {}


def test_schedule_and_rxnorm_results_become_evidence_not_sources():
    book = SourceBook()
    book.add_tool_result("get_schedule", {"ok": True, "data": {"daily": [{"time": "08:00"}]}})
    book.add_tool_result("lookup_rxnorm", {"ok": True, "data": {"ingredient": "furosemide"}})

    assert book.texts == {}
    assert "08:00" in book.evidence[0]
    assert "furosemide" in book.evidence[1]


def test_a_failed_tool_result_is_returned_unchanged():
    book = SourceBook()
    failed = {"ok": False, "error": "The tool input was not valid."}

    assert book.add_tool_result("search_patient_document", failed) is failed
    assert book.texts == {}


def test_only_a_successful_paper_search_can_establish_that_the_papers_were_checked():
    from app.qa.sources import SourceBook

    sources = SourceBook()
    sources.add_tool_result("search_patient_document", {"ok": False, "error": "unavailable"})
    assert not sources.paper_search_completed
    sources.add_tool_result("search_patient_document", {"ok": True, "data": {"passages": []}})
    assert sources.paper_search_completed
