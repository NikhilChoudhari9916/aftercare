"""Ask answers a plain purpose question from the papers first, then the FDA label (ADR-0048)."""

import pytest
from fastapi import FastAPI

from app.agents.question_graph import Route
from app.auth.dependencies import DbSession
from app.enrichment.cache import ExternalError
from app.enrichment.openfda import LabelText
from app.memory.session import Recall, Turn, get_session_memory
from app.qa.factory import build_openfda_client
from app.qa.label_purpose import (
    LABEL_EXCERPT_CHARS,
    answer_purpose,
    label_excerpt,
    purpose_medicine,
)
from app.qa.retriever import Retriever
from app.qa.routes import ToolClients, get_question_llm, get_retriever, get_tool_clients
from app.safety.messages import NO_CARE_TEAM_LINE
from app.safety.rules import Tier
from app.tools.paper_medicines import MedicineEntry
from tests.auth.helpers import make_settings
from tests.fakes import FakeLLM
from tests.qa.test_ask_api import ask, reply
from tests.summary.helpers import confirmed

FUROSEMIDE_PURPOSE = (
    "INDICATIONS AND USAGE Edema Furosemide tablets are indicated in adults and pediatric "
    "patients for the treatment of edema associated with congestive heart failure, cirrhosis of "
    "the liver, and renal disease, including the nephrotic syndrome. Furosemide tablets are "
    "particularly useful when an agent with greater diuretic potential is desired. Hypertension "
    "Oral furosemide may be used in adults for the treatment of hypertension alone or in "
    "combination with other antihypertensive agents."
)


def label(purpose: str | None = FUROSEMIDE_PURPOSE, found: bool = True) -> LabelText:
    return LabelText(found=found, medicine="furosemide", purpose=purpose)


class FakeOpenFda:
    """Stands in for the FDA service: no network, and every lookup is recorded."""

    def __init__(self, result: LabelText | Exception) -> None:
        self._result = result
        self.lookups: list[list[str]] = []

    def get_label(self, names: list[str]) -> LabelText:
        self.lookups.append(names)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


# --- which questions count, and which medicine they are about ---


@pytest.mark.parametrize(
    "question",
    [
        "What does furosemide do",
        "what does furosemide do?",
        "What is furosemide for?",
        "What is Lasix for",
        "What's furosemide used for?",
        "Why am I taking furosemide?",
    ],
)
def test_a_plain_purpose_question_about_one_confirmed_medicine_is_recognised(question):
    assert purpose_medicine(confirmed(), question, Recall()) == "furosemide"


@pytest.mark.parametrize(
    "question",
    [
        "What is my water pill for?",  # names no medicine: the regular workflow handles it
        "What is warfarin for?",  # not one of this patient's confirmed medicines
        "What does furosemide do to my kidneys?",  # a different question
        "What is the dose for furosemide?",
        "What is furosemide for and when do I take it?",
        "What are furosemide and lisinopril for?",  # two medicines: do not guess
        "When do I take furosemide?",
    ],
)
def test_other_questions_keep_the_regular_workflow(question):
    assert purpose_medicine(confirmed(), question, Recall()) is None


def test_it_means_the_medicine_the_last_turn_named():
    recall = Recall(
        turns=(Turn(question="What is furosemide also called?", answer="x", focus_medicine=None),)
    )

    assert purpose_medicine(confirmed(), "What is it for?", recall) == "furosemide"
    assert purpose_medicine(confirmed(), "What is it for?", Recall()) is None


# --- the words shown from the label ---


def test_the_heading_is_removed_but_the_labels_words_are_kept():
    text = label_excerpt(FUROSEMIDE_PURPOSE)

    assert text.startswith("Edema Furosemide tablets are indicated in adults")
    assert "congestive heart failure, cirrhosis of the liver, and renal disease" in text
    assert "INDICATIONS AND USAGE" not in text


def test_a_long_section_stops_at_a_sentence_end_and_says_it_goes_on():
    text = label_excerpt(FUROSEMIDE_PURPOSE)

    assert text.endswith("diuretic potential is desired. …")
    assert len(text) <= LABEL_EXCERPT_CHARS + 2
    assert "Hypertension Oral" not in text


def test_a_short_section_is_shown_whole_with_no_ellipsis():
    assert label_excerpt("1 INDICATIONS AND USAGE Used to treat swelling.") == (
        "Used to treat swelling."
    )


def test_section_numbers_and_cross_references_are_removed():
    text = label_excerpt(
        "1.1 Hypertension Lisinopril is indicated for the treatment of hypertension ( 1.1 ) "
        "and heart failure ( 1.2, 1.3 )."
    )

    assert text == (
        "Hypertension Lisinopril is indicated for the treatment of hypertension and heart failure ."
    )


def test_label_text_cannot_make_a_fake_source_tag_or_bold_text():
    text = label_excerpt("Treats swelling [D1] and **everything** else.")

    assert "[" not in text and "]" not in text and "*" not in text


def test_a_long_label_without_sentence_ends_is_cut_at_a_word():
    text = label_excerpt("word " * 200)

    assert text.endswith("word …") and len(text) <= LABEL_EXCERPT_CHARS + 2


# --- the reply ---


def test_the_papers_win_when_they_state_the_purpose():
    entry = MedicineEntry(
        id="D2005",
        text="acetaminophen 500 mg as needed for pain",
        page=1,
        section="Original medicine-list entry",
        original_document=True,
        name="acetaminophen",
        status="CONTINUED",
        purpose_quote="acetaminophen 500 mg as needed for pain",
    )

    text, cited = answer_purpose("acetaminophen", entry, label(), "L1", Tier.GENERAL)

    assert "Original words from your papers about acetaminophen" in text
    assert "FDA" not in text
    assert cited == ["D2005"]


def test_without_a_purpose_in_the_papers_the_label_is_general_information():
    text, cited = answer_purpose("furosemide", None, label(), "L1", Tier.GENERAL)

    assert text.startswith("Your papers don't say why you take furosemide.")
    assert "General information from the FDA drug label, in its own words" in text
    assert "Furosemide tablets are indicated in adults" in text
    assert "[L1]" in text
    assert "does not say which one is yours" in text
    assert "ask your care team or your pharmacist" in text
    assert cited == ["L1"]


@pytest.mark.parametrize(
    "unavailable",
    [None, label(found=False), label(purpose=None)],
)
def test_with_no_label_text_it_says_so_and_points_to_a_person(unavailable):
    text, cited = answer_purpose("furosemide", None, unavailable, None, Tier.GENERAL)

    assert "Your papers don't say why you take furosemide." in text
    assert "couldn't get a description from the FDA drug label" in text
    assert "care team or your pharmacist" in text
    assert cited == []


def test_a_tier_2_reply_starts_with_the_care_team_line():
    text, _ = answer_purpose("furosemide", None, label(), "L1", Tier.CARE_TEAM)

    assert text.startswith(NO_CARE_TEAM_LINE)


# --- through the real Ask endpoint ---


@pytest.fixture
def fda(app: FastAPI, llm: FakeLLM):
    """No real model and no real FDA service. The test picks what the FDA service answers."""
    get_session_memory.cache_clear()
    holder: dict[str, FakeOpenFda] = {}

    def use(result: LabelText | Exception) -> FakeOpenFda:
        holder["client"] = FakeOpenFda(result)
        app.dependency_overrides[get_tool_clients] = lambda: ToolClients(
            rxnorm=None, openfda=holder["client"]
        )
        return holder["client"]

    app.dependency_overrides[get_question_llm] = lambda: llm
    app.dependency_overrides[get_retriever] = _keyword_retriever
    yield use
    get_session_memory.cache_clear()


def _keyword_retriever(db: DbSession) -> Retriever:
    return Retriever(db)


def safe_gate(llm: FakeLLM) -> None:
    """The three safety readings for an ordinary question."""
    for _ in range(3):
        llm.queue_reply(reply("TIER 3"))


def model_calls(llm: FakeLLM, since: int) -> list[str]:
    """What the model was asked to do after `since` calls had already been made (the setup)."""
    return [call["kind"] for call in llm.calls[since:]]


def test_ask_answers_what_a_medicine_does_from_the_label_when_the_papers_do_not(
    client, confirmed_patient, llm, fda
):
    openfda = fda(label())
    safe_gate(llm)
    setup_calls = len(llm.calls)

    response = ask(client, confirmed_patient, "What does furosemide do")

    body = response.json()
    assert response.status_code == 200 and body["outcome"] == "answered"
    assert "Your papers don't say why you take furosemide." in body["answer"]
    assert "General information from the FDA drug label" in body["answer"]
    assert "congestive heart failure" in body["answer"]
    assert [c["kind"] for c in body["citations"]] == ["label"]
    assert body["citations"][0]["label"] == "From the drug label"
    # Only the medicine's own names went out: nothing from the patient or the question.
    assert openfda.lookups == [["furosemide", "LASIX"]]
    # The model only did the three safety readings. It wrote none of this reply.
    assert model_calls(llm, setup_calls) == ["complete"] * 3


def test_ask_prefers_the_papers_when_they_state_the_purpose(client, confirmed_patient, llm, fda):
    openfda = fda(label())
    safe_gate(llm)

    body = ask(client, confirmed_patient, "What is acetaminophen for?").json()

    assert "Original words from your papers about acetaminophen" in body["answer"]
    assert [c["kind"] for c in body["citations"]] == ["paper"]
    assert openfda.lookups == []  # the papers answered, so nothing was looked up


def test_a_label_service_that_is_down_gives_a_plain_answer_not_an_error(
    client, confirmed_patient, llm, fda
):
    fda(ExternalError("The drug label service is not reachable right now."))
    safe_gate(llm)

    response = ask(client, confirmed_patient, "What is furosemide for?")

    assert response.status_code == 200
    answer = response.json()["answer"]
    assert "couldn't get a description from the FDA drug label" in answer
    assert response.json()["citations"] == []


def test_a_medicine_that_is_not_the_patients_is_never_looked_up(
    client, confirmed_patient, llm, fda
):
    openfda = fda(label())
    safe_gate(llm)
    llm.queue_extraction(  # the router: out of scope, so nothing else is called
        Route(route="OUT_OF_SCOPE", rewritten_question="What is warfarin for?")
    )

    ask(client, confirmed_patient, "What is warfarin for?")

    assert openfda.lookups == []


def test_an_emergency_still_gets_only_the_fixed_911_words(client, confirmed_patient, llm, fda):
    openfda = fda(label())

    body = ask(client, confirmed_patient, "What does furosemide do? My chest hurts badly").json()

    assert body["outcome"] == "emergency"
    assert openfda.lookups == []


# --- the switch ---


def test_the_lookup_can_be_switched_off_and_on():
    assert build_openfda_client(make_settings(fda_label_lookup=False)) is None
    assert build_openfda_client(make_settings(fda_label_lookup=True)) is not None
