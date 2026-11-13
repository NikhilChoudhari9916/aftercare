import httpx
import pytest

from app.enrichment.cache import ExternalError, TtlCache
from app.enrichment.openfda import OpenFdaClient

LABEL = {
    "set_id": "01a5f094-b473-4e46-9e61-69d5ec6dd766",
    "effective_time": "20230301",
    "indications_and_usage": ["INDICATIONS AND USAGE Edema Furosemide treats swelling."],
    "warnings": ["WARNING Furosemide is a potent diuretic.", "It can cause water loss."],
    "boxed_warning": ["Do not use more than told."],
    "dosage_and_administration": ["DOSAGE: Take 400 mg every hour."],
    "openfda": {"generic_name": ["FUROSEMIDE"]},
}


class Service:
    """A pretend openFDA: `labels` maps a search text to the label it finds."""

    def __init__(self, labels: dict[str, dict], status: int = 200) -> None:
        self.labels = labels
        self.status = status
        self.searches: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        search = request.url.params["search"]
        self.searches.append(search)
        if self.status != 200:
            return httpx.Response(self.status)
        label = self.labels.get(search)
        if label is None:
            return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})
        return httpx.Response(200, json={"results": [label]})


def client(service: Service, max_chars: int = 1500) -> OpenFdaClient:
    http = httpx.Client(transport=httpx.MockTransport(service))
    return OpenFdaClient(http, "https://fda.test", TtlCache(3600), max_chars)


FOUND = {'openfda.generic_name:"furosemide"': LABEL}


def test_the_label_gives_purpose_warnings_and_where_it_came_from():
    label = client(Service(FOUND)).get_label(["furosemide"])

    assert label.found
    assert label.purpose == "INDICATIONS AND USAGE Edema Furosemide treats swelling."
    assert label.warnings == "WARNING Furosemide is a potent diuretic. It can cause water loss."
    assert label.boxed_warning == "Do not use more than told."
    assert label.source_url.endswith("setid=01a5f094-b473-4e46-9e61-69d5ec6dd766")
    assert label.label_date == "20230301"


def test_dosage_never_reaches_the_result():
    label = client(Service(FOUND)).get_label(["furosemide"])

    assert "400 mg" not in label.model_dump_json()
    assert "DOSAGE" not in label.model_dump_json()


def test_the_brand_name_is_tried_when_the_generic_name_finds_nothing():
    service = Service({'openfda.brand_name:"LASIX"': LABEL})

    label = client(service).get_label(["furosemide", "LASIX"])

    assert label.found
    assert label.medicine == "LASIX"
    assert service.searches == [
        'openfda.generic_name:"furosemide"',
        'openfda.brand_name:"furosemide"',
        'openfda.generic_name:"LASIX"',
        'openfda.brand_name:"LASIX"',
    ]


def test_a_label_for_the_medicine_alone_beats_a_combination_product():
    combo = {
        **LABEL,
        "indications_and_usage": ["Treats high blood pressure with a second drug."],
        "openfda": {"generic_name": ["LISINOPRIL AND HYDROCHLOROTHIAZIDE"]},
    }
    alone = {**LABEL, "openfda": {"generic_name": ["LISINOPRIL"]}}

    def both(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [combo, alone]})

    http = httpx.Client(transport=httpx.MockTransport(both))
    openfda = OpenFdaClient(http, "https://fda.test", TtlCache(3600))

    assert openfda.get_label(["lisinopril"]).purpose == LABEL["indications_and_usage"][0]


def test_the_first_label_is_used_when_none_is_for_the_medicine_alone():
    combo = {**LABEL, "openfda": {"generic_name": ["A AND B"]}}

    def only_combo(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [combo]})

    http = httpx.Client(transport=httpx.MockTransport(only_combo))
    openfda = OpenFdaClient(http, "https://fda.test", TtlCache(3600))

    assert openfda.get_label(["a"]).found


def test_a_medicine_without_a_label_is_reported_as_not_found():
    label = client(Service({})).get_label(["zzzz"])

    assert not label.found
    assert label.purpose is None


def test_warnings_and_cautions_is_used_when_there_is_no_warnings_part():
    newer = {k: v for k, v in LABEL.items() if k != "warnings"}
    newer["warnings_and_cautions"] = ["Low blood pressure can happen."]

    label = client(Service({'openfda.generic_name:"x"': newer})).get_label(["x"])

    assert label.warnings == "Low blood pressure can happen."


def test_a_long_section_is_shortened_at_a_word():
    long_label = {**LABEL, "indications_and_usage": ["word " * 1000]}

    label = client(Service({'openfda.generic_name:"x"': long_label}), max_chars=50).get_label(["x"])

    assert len(label.purpose) <= 54
    assert label.purpose.endswith("word ...")


def test_a_quote_mark_in_the_name_cannot_change_the_search():
    service = Service({})
    client(service).get_label(['x" OR openfda.brand_name:"y'])

    assert all(search.count('"') == 2 for search in service.searches)


def test_the_same_medicine_is_looked_up_once():
    service = Service(FOUND)
    openfda = client(service)
    openfda.get_label(["furosemide"])
    asked = len(service.searches)

    openfda.get_label(["Furosemide"])

    assert len(service.searches) == asked


def test_a_service_that_is_down_raises_a_plain_error():
    with pytest.raises(ExternalError, match="not reachable"):
        client(Service(FOUND, status=500)).get_label(["furosemide"])


def test_no_names_means_nothing_to_look_up():
    service = Service(FOUND)
    assert not client(service).get_label([" "]).found
    assert service.searches == []
