from app.tools import default_registry


def run(name, context, arguments):
    return default_registry().run(name, arguments, context)


def test_a_confirmed_medicine_gets_its_label_purpose_and_warnings(
    confirmed_patient, context_for, outside
):
    result = run("search_fda_label", context_for(confirmed_patient), {"medicine": "furosemide"})

    assert result["ok"]
    assert result["data"]["purpose"] == "Treats swelling."
    assert result["data"]["warnings"] == "Can cause low potassium."
    assert "400 mg" not in str(result)  # dosage is never passed on


def test_a_brand_name_from_the_papers_works_too(confirmed_patient, context_for):
    result = run("search_fda_label", context_for(confirmed_patient), {"medicine": "lasix"})

    assert result["ok"]


def test_a_medicine_that_is_not_in_the_papers_is_refused_without_asking_the_service(
    confirmed_patient, context_for, outside
):
    result = run("search_fda_label", context_for(confirmed_patient), {"medicine": "ibuprofen"})

    assert result == {"ok": False, "error": "That is not one of the patient's confirmed medicines."}
    assert outside.requests == []


def test_a_label_lookup_that_cannot_reach_the_service_says_so(
    confirmed_patient, context_for, outside
):
    outside.down = True

    result = run("search_fda_label", context_for(confirmed_patient), {"medicine": "furosemide"})

    assert result["ok"] is False
    assert "not reachable" in result["error"]


def test_a_label_lookup_without_the_service_set_up_says_so(confirmed_patient, context_for):
    context = context_for(confirmed_patient, openfda=None)

    assert not run("search_fda_label", context, {"medicine": "furosemide"})["ok"]


def test_rxnorm_gives_the_ids_and_names(confirmed_patient, context_for):
    result = run("lookup_rxnorm", context_for(confirmed_patient), {"name": "furosemide"})

    assert result["ok"]
    assert result["data"]["rxcui"] == "4603"
    assert result["data"]["ingredient"] == "furosemide"


def test_rxnorm_cannot_reach_the_service_or_is_not_set_up(confirmed_patient, context_for, outside):
    outside.down = True
    down = run("lookup_rxnorm", context_for(confirmed_patient), {"name": "furosemide"})
    assert not down["ok"]
    assert "not reachable" in down["error"]

    missing = context_for(confirmed_patient, rxnorm=None)
    assert not run("lookup_rxnorm", missing, {"name": "furosemide"})["ok"]


def test_rxnorm_only_takes_a_short_name(confirmed_patient, context_for, outside):
    context = context_for(confirmed_patient)

    assert not run("lookup_rxnorm", context, {"name": "x" * 81})["ok"]
    assert outside.requests == []
