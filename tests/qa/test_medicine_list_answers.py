"""Common list questions use original table facts, without a generated medical explanation."""

import json

import pytest
from sqlmodel import select

from app.models import DocumentPage, ProfileItem, QALog
from app.qa.medicine_answers import medicine_question
from app.safety.messages import TIER1_MESSAGE
from app.tools.paper_medicines import READ_ORIGINAL_MEDICINE_ENTRIES
from app.tools.registry import ToolContext, ToolRegistry
from tests.documents.test_upload_api import decide_all
from tests.qa.test_ask_api import ask, pretend_outside, reply  # noqa: F401


def rows(db, patient_id):
    return ToolRegistry([READ_ORIGINAL_MEDICINE_ENTRIES]).run(
        "read_original_medicine_entries", {}, ToolContext(db=db, patient_id=patient_id)
    )


@pytest.mark.parametrize(
    "question,intent",
    [
        ("Which medicine is new?", "new"),
        ("Which medications are new?", "new"),
        ("What is each of my medicines for?", "purposes"),
        ("What are my medicines used for?", "purposes"),
        ("What are my medicines", "list"),
        ("what are my medications?", "list"),
        ("What medicines am I taking?", "list"),
        ("List my medicines", "list"),
        ("What are my meds?", "list"),
        ("What are my medicines doing to me?", None),
        ("What are the side effects of my medicines?", None),
        ("Should I start a new medicine?", None),
        ("What is metoprolol for?", None),
        ("Which medicine is new? I have chest pain", None),
    ],
)
def test_only_explicit_list_questions_use_the_fixed_path(question, intent):
    assert medicine_question(question) == intent


def test_new_status_and_purpose_are_read_from_original_rows(db, confirmed_patient):
    result = rows(db, confirmed_patient)
    assert result["ok"]
    entries = result["data"]["passages"]
    assert len(entries) == 6
    new = [e for e in entries if e["status"] == "NEW"]
    assert {e["name"] for e in new} == {"metoprolol succinate ER", "potassium chloride ER"}
    assert all("NEW" in e["text"] and e["original_document"] for e in new)
    pain = next(e for e in entries if e["name"] == "acetaminophen")
    assert "as needed for pain" in pain["purpose_quote"]
    assert "3,000 mg" in pain["purpose_quote"]  # do not crop away the maximum-dose warning
    assert all(e["purpose_quote"] is None for e in entries if e["name"] != "acetaminophen")
    pages = {
        p.number: " ".join(p.text.split())
        for p in db.exec(
            select(DocumentPage).where(DocumentPage.patient_id == confirmed_patient)
        ).all()
    }
    assert all(e["text"] in pages[e["page"]] for e in entries)


@pytest.mark.parametrize(
    "question", ["Which medicine is new?", "What is each of my medicines for?"]
)
def test_the_reported_questions_work_without_an_answering_or_review_model(
    client, db, confirmed_patient, llm, question
):
    before = len(llm.calls)
    for _ in range(3):
        llm.queue_reply(reply("TIER 3"))
    response = ask(client, confirmed_patient, question)
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "answered" and body["tier"] == 3
    assert "I can't answer that safely" not in body["answer"]
    calls = llm.calls[before:]
    assert len(calls) == 3 and all(c["kind"] == "complete" and not c["tools"] for c in calls)
    assert body["citations"] and all(c["kind"] == "paper" for c in body["citations"])
    if "new" in question:
        assert "metoprolol succinate ER" in body["answer"]
        assert "potassium chloride ER" in body["answer"]
        assert "lisinopril" not in body["answer"]
    else:
        assert "as needed for pain" in body["answer"] and "3,000 mg" in body["answer"]
        assert body["answer"].count("couldn't verify a purpose") == 5
        assert "amlodipine** (marked STOPPED)" in body["answer"]
        assert "helps you sleep" not in body["answer"]
    log = db.exec(select(QALog)).one()
    assert log.task == "PAPER_LIST" and log.tool_calls == 1 and log.attempts == 0
    assert "metoprolol" not in str(log.model_dump())


def test_profile_text_cannot_supply_a_purpose_or_change_original_new_status(db, confirmed_patient):
    item = next(
        i
        for i in db.exec(
            select(ProfileItem).where(ProfileItem.patient_id == confirmed_patient)
        ).all()
        if json.loads(i.data).get("name_as_written") == "metoprolol succinate ER"
    )
    data = json.loads(item.data)
    data.update(status="CONTINUED", source_quote="Metoprolol is used for sleep.")
    item.data = json.dumps(data)
    db.add(item)
    db.commit()
    result = rows(db, confirmed_patient)
    medicine = next(e for e in result["data"]["passages"] if e["name"] == "metoprolol succinate ER")
    assert medicine["status"] == "NEW" and medicine["purpose_quote"] is None
    assert "sleep" not in medicine["text"]


def test_a_negative_purpose_sentence_does_not_become_a_positive_purpose(db, confirmed_patient):
    page = db.exec(
        select(DocumentPage).where(
            DocumentPage.patient_id == confirmed_patient, DocumentPage.number == 1
        )
    ).one()
    page.text = page.text.replace(
        "Take 1 to 2 tablets by mouth every 6 hours as needed for pain.",
        "Do not take this medicine as needed for pain.",
    )
    db.add(page)
    db.commit()
    result = rows(db, confirmed_patient)
    medicine = next(e for e in result["data"]["passages"] if e["name"] == "acetaminophen")
    assert medicine["purpose_quote"] is None


def test_an_incomplete_extraction_cannot_claim_to_list_every_new_medicine(db, confirmed_patient):
    item = next(
        i
        for i in db.exec(
            select(ProfileItem).where(ProfileItem.patient_id == confirmed_patient)
        ).all()
        if json.loads(i.data).get("name_as_written") == "metoprolol succinate ER"
    )
    db.delete(item)
    db.commit()
    assert not rows(db, confirmed_patient)["ok"]


def test_unrecognized_table_format_uses_the_regular_path(db, confirmed_patient):
    page = db.exec(
        select(DocumentPage).where(
            DocumentPage.patient_id == confirmed_patient, DocumentPage.number == 1
        )
    ).one()
    page.text = page.text.replace("Your medicine list", "Unrecognized format")
    db.add(page)
    db.commit()
    assert not rows(db, confirmed_patient)["ok"]


def test_edit_comparisons_and_emergency_handling_still_take_precedence(client, db, ready, llm):
    patient_id, extraction = ready
    medicine = next(i for i in extraction["items"] if i["section"] == "medicines")
    response = client.put(
        f"/patients/{patient_id}/profile",
        json=decide_all(
            extraction, **{medicine["id"]: {"data": {**medicine["data"], "dose": "37 mg"}}}
        ),
    )
    assert response.status_code == 200 and not rows(db, patient_id)["ok"]
    for _ in range(3):
        llm.queue_reply(reply("TIER 3"))
    assert ask(client, patient_id, "Which medicine is new?").json()["outcome"] == "conflict"
    body = ask(client, patient_id, "Which medicine is new? My chest hurts badly").json()
    assert body["outcome"] == "emergency" and body["answer"] == TIER1_MESSAGE


def test_a_pronoun_without_a_medicine_identity_asks_for_clarification_without_guessing(
    client, confirmed_patient, llm
):
    from app.qa.grounding import CLARIFY_MEDICINE

    before = len(llm.calls)
    for _ in range(3):
        llm.queue_reply(reply("TIER 3"))
    body = ask(client, confirmed_patient, "When do my papers say to take it?").json()
    assert body["outcome"] == "answered" and body["answer"] == CLARIFY_MEDICINE
    assert body["citations"] == []
    assert len(llm.calls[before:]) == 3


def test_the_original_medicine_entry_tool_cannot_cross_patient_boundaries(db, confirmed_patient):
    from tests.qa.conftest import other_patient

    other = other_patient(db)
    page = db.exec(select(DocumentPage).where(DocumentPage.patient_id == other)).one()
    page.text = "Discharge medications\nwarfarin (COUMADIN) 5 mg\nTake as written.\nNEW"
    db.add(page)
    db.commit()
    theirs = rows(db, other)
    ours = rows(db, confirmed_patient)
    assert theirs["ok"] and ours["ok"]
    assert "warfarin" in str(theirs["data"]) and "furosemide" not in str(theirs["data"])
    assert "furosemide" in str(ours["data"]) and "warfarin" not in str(ours["data"])


def test_a_no_new_medicine_reply_keeps_the_tier_2_care_instruction():
    from app.qa.medicine_answers import answer_medicine_list
    from app.safety.messages import NO_CARE_TEAM_LINE
    from app.safety.rules import Tier
    from app.tools.paper_medicines import MedicineEntries

    reply = answer_medicine_list(MedicineEntries(passages=[]), "new", Tier.CARE_TEAM)
    assert reply.startswith(NO_CARE_TEAM_LINE)
    assert "couldn't verify" in reply


def test_what_are_my_medicines_lists_every_original_row_without_a_model(
    client, db, confirmed_patient, llm
):
    before = len(llm.calls)
    for _ in range(3):
        llm.queue_reply(reply("TIER 3"))

    response = ask(client, confirmed_patient, "What are my medicines")

    body = response.json()
    assert response.status_code == 200 and body["outcome"] == "answered"
    assert "I can't answer that safely" not in body["answer"]
    for name in (
        "furosemide",
        "metoprolol succinate ER",
        "potassium chloride ER",
        "lisinopril",
        "acetaminophen",
        "amlodipine",
    ):
        assert f"**{name}**" in body["answer"]
    assert "**amlodipine** — marked **STOPPED**" in body["answer"]
    assert "**metoprolol succinate ER** — marked **NEW**" in body["answer"]
    assert len(body["citations"]) == 6 and all(c["kind"] == "paper" for c in body["citations"])
    calls = llm.calls[before:]  # only the three safety readings: the model wrote none of it
    assert len(calls) == 3 and all(c["kind"] == "complete" and not c["tools"] for c in calls)
    log = db.exec(select(QALog)).one()
    assert log.task == "PAPER_LIST" and log.attempts == 0


def test_a_medicine_list_reply_keeps_the_tier_2_care_instruction():
    from app.qa.medicine_answers import answer_medicine_list
    from app.safety.messages import NO_CARE_TEAM_LINE
    from app.safety.rules import Tier
    from app.tools.paper_medicines import MedicineEntries, MedicineEntry

    entry = MedicineEntry(
        id="D2001",
        text="lisinopril 10 mg CONTINUE",
        page=1,
        section="Original medicine-list entry",
        original_document=True,
        name="lisinopril",
        status="CONTINUE",
        purpose_quote=None,
    )

    reply = answer_medicine_list(MedicineEntries(passages=[entry]), "list", Tier.CARE_TEAM)

    assert reply.startswith(NO_CARE_TEAM_LINE)
    assert "**lisinopril** — marked **CONTINUE**. [D2001]" in reply
