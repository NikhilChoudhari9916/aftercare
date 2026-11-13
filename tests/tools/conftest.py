import httpx
import pytest
from sqlmodel import Session

from app.enrichment.cache import TtlCache
from app.enrichment.openfda import OpenFdaClient
from app.enrichment.rxnorm import RxNormClient
from app.tools.registry import ToolContext
from tests.summary.conftest import confirmed_patient  # noqa: F401  (fixture: Patient 1, confirmed)


class Outside:
    """Pretend RxNorm and openFDA in one place. Remembers every request so a test can count them."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.down = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            return httpx.Response(503)
        if request.url.host == "fda.test":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "set_id": "abc",
                            "indications_and_usage": ["Treats swelling."],
                            "warnings": ["Can cause low potassium."],
                            "dosage_and_administration": ["Take 400 mg every hour."],
                        }
                    ]
                },
            )
        if request.url.path.endswith("/rxcui.json"):
            return httpx.Response(200, json={"idGroup": {"rxnormId": ["4603"]}})
        return httpx.Response(
            200,
            json={
                "relatedGroup": {
                    "conceptGroup": [
                        {
                            "tty": "IN",
                            "conceptProperties": [{"rxcui": "4603", "name": "furosemide"}],
                        }
                    ]
                }
            },
        )


@pytest.fixture
def outside() -> Outside:
    return Outside()


@pytest.fixture
def context_for(db: Session, outside: Outside):
    """Builds a tool context for any patient, with pretend outside services."""
    http = httpx.Client(transport=httpx.MockTransport(outside))

    def build(patient_id: str, **changes) -> ToolContext:
        fields = {
            "rxnorm": RxNormClient(http, "https://rxnav.test/REST", TtlCache(3600)),
            "openfda": OpenFdaClient(http, "https://fda.test", TtlCache(3600)),
        }
        fields.update(changes)
        return ToolContext(db=db, patient_id=patient_id, **fields)

    return build
