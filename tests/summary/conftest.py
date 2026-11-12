import pytest
from fastapi.testclient import TestClient

from tests.auth.helpers import FakeProvider
from tests.documents.test_upload_api import decide_all, owner, upload
from tests.fakes import FakeLLM
from tests.samples import patient1_profile


@pytest.fixture
def confirmed_patient(client: TestClient, provider: FakeProvider, llm: FakeLLM) -> str:
    """A signed-in owner whose Patient 1 papers are read and confirmed. Returns the patient ID."""
    patient_id = owner(client, provider)
    llm.queue_extraction(patient1_profile())
    assert upload(client, patient_id).status_code == 202
    extraction = client.get(f"/patients/{patient_id}/extraction").json()
    response = client.put(f"/patients/{patient_id}/profile", json=decide_all(extraction))
    assert response.status_code == 200
    return patient_id
