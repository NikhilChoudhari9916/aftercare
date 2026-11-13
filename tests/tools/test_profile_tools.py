from sqlmodel import Session

from app.extraction.schema import MedStatus
from app.models import Patient, ProfileStatus, User
from app.tools import default_registry
from app.tools.profile_tools import Passage
from tests.samples import medicine
from tests.summary.test_profile import add_version


def second_patient(db: Session) -> str:
    """Another patient with a single medicine of their own."""
    user = User(google_sub="someone-else", email="b@example.com", display_name="Bea")
    db.add(user)
    db.commit()
    patient = Patient(owner_user_id=user.id)
    db.add(patient)
    db.commit()
    secret = medicine("warfarin", ["COUMADIN"], "5 mg", "daily", MedStatus.NEW, "Take warfarin.")
    add_version(db, patient.id, 1, ProfileStatus.CONFIRMED, [(secret, True)])
    return patient.id


def run(name, context, arguments=None):
    return default_registry().run(name, arguments or {}, context)


def test_confirmed_medicines_come_with_their_quotes_and_pages(confirmed_patient, context_for):
    result = run("get_confirmed_medicines", context_for(confirmed_patient))

    assert result["ok"]
    medicines = {m["name_as_written"]: m for m in result["data"]["medicines"]}
    assert len(medicines) == 6
    assert medicines["furosemide"]["dose"] == "40 mg"
    assert medicines["furosemide"]["status"] == "CHANGED"
    assert medicines["furosemide"]["source_quote"].startswith("Take 1 tablet (40 mg)")
    assert medicines["furosemide"]["source_page"] >= 1


def test_nothing_is_returned_before_the_papers_are_confirmed(db, context_for):
    user = User(google_sub="s", email="c@example.com", display_name="Cy")
    db.add(user)
    db.commit()
    patient = Patient(owner_user_id=user.id)
    db.add(patient)
    db.commit()

    for name in ("get_confirmed_medicines", "get_schedule"):
        result = run(name, context_for(patient.id))
        assert result == {"ok": False, "error": "The papers have not been confirmed yet."}


def test_the_schedule_separates_daily_as_needed_and_stopped(confirmed_patient, context_for):
    result = run("get_schedule", context_for(confirmed_patient))

    assert result["ok"]
    data = result["data"]
    assert [m["name"] for m in data["as_needed"]] == ["acetaminophen"]
    assert [m["name"] for m in data["stopped"]] == ["amlodipine"]
    assert data["daily"]
    assert "plan_medicines" not in data
    assert {f["what"] for f in data["follow_ups"]}


def test_a_tool_never_takes_the_patient_from_the_model(confirmed_patient, context_for, db):
    other = second_patient(db)
    ours = context_for(confirmed_patient)

    asked = run("get_confirmed_medicines", ours, {"patient_id": other})

    assert asked["ok"] is False  # the schema has no such field


def test_each_patient_sees_only_their_own_medicines(confirmed_patient, context_for, db):
    other = second_patient(db)

    mine = run("get_confirmed_medicines", context_for(confirmed_patient))
    theirs = run("get_confirmed_medicines", context_for(other))

    assert "warfarin" not in str(mine)
    assert "furosemide" not in str(theirs)
    assert [m["name_as_written"] for m in theirs["data"]["medicines"]] == ["warfarin"]
    their_schedule = str(run("get_schedule", context_for(other)))
    assert "warfarin" in their_schedule
    assert "furosemide" not in their_schedule
    assert "warfarin" not in str(run("get_schedule", context_for(confirmed_patient)))


class FakeSearch:
    def __init__(self, count: int = 6) -> None:
        self.count = count
        self.calls: list[tuple[str, str, int]] = []

    def search(self, patient_id: str, query: str, limit: int) -> list[Passage]:
        self.calls.append((patient_id, query, limit))
        return [
            Passage(id=f"D{i}", page=1, section="Medicines", text="x") for i in range(self.count)
        ]


def test_a_search_uses_the_signed_in_patient_and_returns_at_most_four(
    confirmed_patient, context_for
):
    search = FakeSearch()

    result = run(
        "search_patient_document",
        context_for(confirmed_patient, search=search),
        {"query": "furosemide"},
    )

    assert search.calls == [(confirmed_patient, "furosemide", 4)]
    assert [p["id"] for p in result["data"]["passages"]] == ["D0", "D1", "D2", "D3"]


def test_a_search_cannot_be_pointed_at_another_patient(confirmed_patient, context_for):
    search = FakeSearch()
    context = context_for(confirmed_patient, search=search)

    result = run("search_patient_document", context, {"query": "x", "patient_id": "other"})

    assert result["ok"] is False
    assert search.calls == []


def test_a_search_asks_for_something_and_not_too_much(confirmed_patient, context_for):
    context = context_for(confirmed_patient, search=FakeSearch())

    assert not run("search_patient_document", context, {"query": ""})["ok"]
    assert not run("search_patient_document", context, {"query": "x" * 301})["ok"]


def test_a_search_without_a_retriever_says_so(confirmed_patient, context_for):
    result = run("search_patient_document", context_for(confirmed_patient), {"query": "x"})

    assert result == {"ok": False, "error": "Searching the papers is not available."}
