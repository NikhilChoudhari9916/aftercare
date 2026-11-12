import asyncio
import json

import httpx
import pytest

from tests.ui.test_api_client import SCHEDULE, TOKEN, client_with
from ui.api_client import BackendUnavailable, NotSignedIn, Rejected


def test_saving_a_plan_sends_it_to_the_backend_and_reads_the_new_schedule():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"], seen["path"] = request.method, request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=SCHEDULE)

    plan = {"medicines": [{"item_id": "m1", "times": ["07:30"]}], "visits": []}
    schedule = asyncio.run(client_with(handler).save_plan(TOKEN, "p1", plan))

    assert (seen["method"], seen["path"]) == ("PUT", "/patients/p1/plan")
    assert seen["body"] == plan
    assert schedule.daily[0].medicines[0].name == "lisinopril"


@pytest.mark.parametrize("status", [403, 404, 422])
def test_a_refused_plan_becomes_a_plain_sentence(status):
    detail = "furosemide: your papers say 1 time a day, so please pick 1."
    client = client_with(lambda request: httpx.Response(status, json={"detail": detail}))

    with pytest.raises(Rejected) as error:
        asyncio.run(client.save_plan(TOKEN, "p1", {}))

    assert str(error.value) == detail


def test_saving_a_plan_handles_a_missing_session_and_a_down_backend():
    with pytest.raises(NotSignedIn):
        asyncio.run(client_with(lambda r: httpx.Response(200)).save_plan(None, "p1", {}))
    with pytest.raises(NotSignedIn):
        asyncio.run(client_with(lambda r: httpx.Response(401)).save_plan(TOKEN, "p1", {}))
    with pytest.raises(BackendUnavailable):
        asyncio.run(client_with(lambda r: httpx.Response(500)).save_plan(TOKEN, "p1", {}))


def test_the_schedule_carries_what_the_planning_form_needs():
    body = {
        **SCHEDULE,
        "plan_medicines": [
            {
                "name": "lisinopril",
                "other_names": [],
                "dose": "10 mg",
                "how_often": "once daily in the morning",
                "status": "CONTINUED",
                "end_date": None,
                "source_page": 1,
                "item_id": "m1",
                "times": ["08:00"],
                "suggested_times": ["08:00"],
                "times_needed": 1,
                "chosen": False,
            }
        ],
        "follow_ups": [
            {
                "item_id": "v1",
                "what": "Cardiology",
                "when": "10/20/2026 at 10:30 a.m.",
                "with_whom": None,
                "kind": "booked_time",
                "papers_date": "2026-10-20",
                "papers_time": "10:30",
                "status": None,
                "date": "2026-10-20",
                "time": "10:30",
                "call_on": None,
                "chosen": False,
                "in_calendar": True,
                "source_page": 3,
            }
        ],
    }
    client = client_with(lambda request: httpx.Response(200, json=body))

    schedule = asyncio.run(client.get_schedule(TOKEN, "p1"))

    assert schedule.plan_medicines[0].times_needed == 1
    assert schedule.follow_ups[0].kind == "booked_time"
