import httpx
import pytest

from app.enrichment.cache import ExternalError, TtlCache
from app.enrichment.rxnorm import RxNormClient

# Trimmed copies of what the real RxNorm service sent back on 2026-11-13.
LASIX = {"idGroup": {"rxnormId": ["202991"]}}
FUROSEMIDE = {"idGroup": {"rxnormId": ["4603"]}}
NOTHING = {"idGroup": {}}
RELATED_LASIX = {
    "relatedGroup": {
        "rxcui": None,
        "conceptGroup": [
            {"tty": "BN", "conceptProperties": [{"rxcui": "202991", "name": "Lasix"}]},
            {"tty": "IN", "conceptProperties": [{"rxcui": "4603", "name": "furosemide"}]},
        ],
    }
}
RELATED_FUROSEMIDE = {
    "relatedGroup": {
        "rxcui": None,
        "conceptGroup": [
            {
                "tty": "BN",
                "conceptProperties": [
                    {"rxcui": "1112198", "name": "Disal"},
                    {"rxcui": "202991", "name": "Lasix"},
                    {"rxcui": "545038", "name": "Salix - substance"},
                ],
            },
            {"tty": "IN", "conceptProperties": [{"rxcui": "4603", "name": "furosemide"}]},
        ],
    }
}
ROUTES = {
    ("/rxcui.json", "Lasix"): LASIX,
    ("/rxcui.json", "furosemide"): FUROSEMIDE,
    ("/rxcui.json", "zzzz"): NOTHING,
    ("/rxcui/202991/related.json", None): RELATED_LASIX,
    ("/rxcui/4603/related.json", None): RELATED_FUROSEMIDE,
}


class Service:
    """A pretend RxNorm that records every request it gets."""

    def __init__(self, status: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self.status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status)
        path = request.url.path.removeprefix("/REST")
        body = ROUTES.get((path, request.url.params.get("name")))
        return httpx.Response(200, json=body if body is not None else NOTHING)


def client(service: Service) -> RxNormClient:
    http = httpx.Client(transport=httpx.MockTransport(service))
    return RxNormClient(http, "https://rxnav.test/REST", TtlCache(3600))


def test_a_brand_name_gives_the_generic_name_and_the_other_brands():
    result = client(Service()).lookup("Lasix")

    assert result.found
    assert result.rxcui == "202991"
    assert result.ingredient == "furosemide"
    assert result.other_names == ["furosemide", "Disal"]  # not Lasix itself, not "- substance"


def test_a_generic_name_gives_its_brands():
    result = client(Service()).lookup("furosemide")

    assert result.ingredient == "furosemide"
    assert result.other_names == ["Disal", "Lasix"]


def test_a_name_that_is_not_known_is_reported_as_not_found():
    result = client(Service()).lookup("zzzz")

    assert not result.found
    assert result.rxcui is None
    assert result.other_names == []


def test_two_terms_are_asked_for_the_way_rxnorm_wants_them():
    service = Service()
    client(service).lookup("furosemide")

    related = [r for r in service.requests if r.url.path.endswith("related.json")]
    assert "tty=BN+IN" in str(related[0].url)


def test_the_second_lookup_of_a_name_is_answered_from_memory():
    service = Service()
    rxnorm = client(service)
    rxnorm.lookup("Lasix")
    asked = len(service.requests)

    rxnorm.lookup("  lasix  ")  # spacing and capital letters do not matter

    assert len(service.requests) == asked


@pytest.mark.parametrize("status", [500, 503])
def test_a_service_that_is_down_raises_a_plain_error_and_is_not_remembered(status):
    service = Service(status=status)
    rxnorm = client(service)
    with pytest.raises(ExternalError, match="not reachable"):
        rxnorm.lookup("Lasix")

    service.status = 200
    assert rxnorm.lookup("Lasix").found


def test_a_connection_failure_raises_the_same_plain_error():
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network")

    rxnorm = RxNormClient(
        httpx.Client(transport=httpx.MockTransport(broken)), "https://rxnav.test/REST", TtlCache(1)
    )
    with pytest.raises(ExternalError):
        rxnorm.lookup("Lasix")
