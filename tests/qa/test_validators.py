from pathlib import Path

import pytest

from app.extraction.schema import ExtractedContact
from app.qa.validators import Check, fallback_message, validate_answer
from app.safety.messages import NO_CARE_TEAM_LINE, TIER1_MESSAGE
from app.safety.rules import Tier
from tests.auth.helpers import make_settings
from tests.summary.helpers import confirmed

RETRIEVED = {
    "D1": (
        "furosemide (also known as LASIX). Dose: 40 mg. How often: once daily in the morning. "
        "Status: CHANGED. What changed: Previously 20 mg once daily."
    ),
    "D2": "Do not take ibuprofen (Advil, Motrin) or naproxen (Aleve). Use acetaminophen (Tylenol).",
    "D4": "Call the cardiology nurse line if you gain more than 2 pounds in one day.",
    "D6": "Cardiology, Dr. A. Rivera, October 20 at 10:30 a.m. Limit sodium to 2,000 mg a day.",
    "L1": "Furosemide can cause the body to lose too much water and salts.",
}
LEAD = "**Call your care team today:** Cardiology Nurse Line, (555) 010-0142."
SETTINGS = make_settings()


def failed(answer: str, tier: Tier = Tier.GENERAL, **changes) -> list[str]:
    arguments = {"profile": confirmed(), "retrieved": RETRIEVED, "settings": SETTINGS}
    arguments.update(changes)
    return validate_answer(answer, tier=tier, **arguments).checks


# --- answers that must pass ---


@pytest.mark.parametrize(
    "answer",
    [
        "Your discharge papers say to take **furosemide, 40 mg, once a day in the morning**. [D1]\n"
        "<followups>\n- What changed?\n</followups>",
        "Your papers say furosemide is now 40 mg once a day. [D1] It was 20 mg before. [D1]",
        "Your papers and drug labels here don't answer this. Please ask your pharmacist.",
        "**Quick question so I get this right:** Which medicine do you mean?",
        "Yes. Your discharge papers list **LASIX as another name for furosemide**. [D1] Please "
        "don't swap it for a store product; your pharmacist can tell you about cheaper options.",
        "Your discharge papers say to see cardiology on October 20 at 10:30 a.m. [D6]",
        "Your papers say to limit sodium to 2000 mg a day. [D6]",
        "Your discharge papers say not to take ibuprofen. [D2]",
        "Your discharge papers say to STOP amlodipine. [D1]",
        "Your papers say you should stop taking amlodipine. [D1]",
        "Please ask your pharmacist whether you should stop it.",
        "MI means a heart attack. Your papers use that word. [D1]",
    ],
)
def test_a_good_answer_passes(answer):
    assert failed(answer) == []


def test_a_care_team_answer_that_leads_with_the_contact_passes():
    answer = (
        f"{LEAD}\nYour discharge papers say to call if you gain more than 2 pounds in one day. [D4]"
    )

    assert failed(answer, Tier.CARE_TEAM) == []


def test_the_gates_own_care_team_line_also_passes():
    line = (
        "Please call Cardiology Nurse Line at (555) 010-0142 (Monday to Friday, 8 a.m. to 5 p.m.)."
    )

    assert (
        failed(
            f"{line} Your discharge papers say to call if you gain weight fast. [D4]",
            Tier.CARE_TEAM,
        )
        == []
    )


# --- empty and emergency ---


def test_an_empty_answer_or_one_with_only_analysis_fails():
    assert failed("") == ["EMPTY"]
    assert failed("<analysis>thinking</analysis>") == ["EMPTY"]
    assert failed("<analysis>never closed. Take it daily. [D1]") == ["EMPTY"]


def test_an_emergency_gets_exactly_the_fixed_words():
    assert failed(TIER1_MESSAGE, Tier.EMERGENCY) == []
    assert failed(f"<analysis>x</analysis>\n{TIER1_MESSAGE}", Tier.EMERGENCY) == []
    assert failed("Please call 911.", Tier.EMERGENCY) == ["NOT_EMERGENCY_TEXT"]
    assert failed(TIER1_MESSAGE + " Rest first.", Tier.EMERGENCY) == ["NOT_EMERGENCY_TEXT"]


# --- citations ---


def test_a_source_the_model_was_not_given_is_refused():
    assert failed("Your papers say take furosemide daily. [D9]") == ["UNKNOWN_CITATION"]
    assert failed("Your papers say take furosemide daily. [D1]") == []


@pytest.mark.parametrize(
    "answer",
    [
        "Your papers say to take furosemide in the morning.",
        "Your papers say to weigh yourself at 7 each day.",
        "Furosemide is a water pill. [D1] Take it daily.",
    ],
)
def test_a_sentence_with_a_fact_and_no_source_tag_is_refused(answer):
    assert Check.UNCITED_FACT in failed(answer)


def test_sentences_with_no_fact_in_them_need_no_tag():
    answer = "I hope that helps. Is there anything else you want to know?"

    assert failed(answer) == []


def test_the_care_team_phone_number_is_not_a_claim_that_needs_a_source():
    assert failed(f"{LEAD}\nPlease call soon.", Tier.CARE_TEAM) == []


# --- doses and times ---


@pytest.mark.parametrize(
    "answer",
    [
        "Your papers say to take furosemide, 80 mg, daily. [D1]",
        "Your papers say to take furosemide, 4 tablets, daily. [D1]",
    ],
)
def test_an_amount_that_is_in_no_source_is_refused(answer):
    assert Check.DOSE_MISMATCH in failed(answer)


def test_another_medicines_dose_in_a_sentence_about_this_one_is_refused():
    # 25 mg is metoprolol's dose in these papers, not furosemide's
    answer = "Your papers say to take furosemide, 25 mg, daily. [D1]"
    swapped = failed(answer, retrieved={**RETRIEVED, "D1": RETRIEVED["D1"] + " 25 mg"})

    assert Check.DOSE_MISMATCH in swapped


def test_the_old_dose_in_the_papers_change_note_is_allowed():
    assert failed("Your papers say it was 20 mg before. [D1]") == []


def test_an_amount_is_matched_whatever_the_spacing_and_commas():
    assert failed("Your papers say to limit sodium to 2,000 mg. [D6]") == []
    assert failed("Your papers say to limit sodium to 2000mg. [D6]") == []


def test_a_time_not_in_the_papers_or_schedule_is_refused():
    assert Check.TIME_MISMATCH in failed("Your papers say to see cardiology at 3 pm. [D6]")
    assert failed("Your papers say to see cardiology at 10:30 am. [D6]") == []
    assert failed("Your papers say to see cardiology at 10:30 a.m. [D6]") == []


def test_the_schedules_everyday_times_are_allowed():
    assert failed("Your reminder is at 8 am. [D1]") == []
    assert failed("Your evening reminder is at 18:00. [D1]") == []


# --- medicine names ---


def test_a_medicine_that_is_not_in_the_papers_or_sources_is_refused():
    assert Check.UNKNOWN_MEDICINE in failed("Your papers mention warfarin. [D1]")
    assert Check.UNKNOWN_MEDICINE in failed("Your papers say ibuprofen is fine. [D1]")


def test_a_medicine_named_in_a_source_may_be_named_in_the_answer():
    assert Check.UNKNOWN_MEDICINE not in failed("Your papers say not to take ibuprofen. [D2]")


# --- advice and diagnosis ---


@pytest.mark.parametrize(
    "sentence",
    [
        "It's ok to skip one dose.",
        "It is fine to stop it for a day.",
        "You can safely skip tonight's pill.",
        "Go ahead and double up.",
        "You should stop taking it.",
        "You could take extra if you feel worse.",
        "Stop taking it now.",
        "Skip your dose tonight.",
        "You can take 2 tablets.",
        "Up to 4 tablets is fine.",
        "You can buy a cheaper version at the store.",
        "Try buying a generic.",
        "You may reduce the dose.",
        "You should stop it, your pharmacist agrees.",
    ],
)
def test_advice_to_change_a_medicine_or_buy_something_is_refused(sentence):
    assert Check.MEDICINE_ADVICE in failed(f"{sentence} [D1]")


@pytest.mark.parametrize(
    "sentence",
    [
        "You probably have an infection.",
        "You have a blood clot.",
        "This could be a blood clot.",
        "That sounds like a heart attack.",
        "It looks like a reaction.",
        "It may be caused by the new medicine.",
        "This is a sign of a clot.",
        "That means you have heart failure.",
    ],
)
def test_saying_what_the_patient_has_or_what_is_causing_it_is_refused(sentence):
    assert Check.DIAGNOSIS in failed(f"{sentence} [D1]")


def test_ordinary_sentences_that_share_words_with_a_diagnosis_are_not_refused():
    assert failed("It may be easier to take it with food. [D1]") == []
    assert failed("You have a visit on October 20. [D6]") == []


# --- size and reading level ---


def test_an_answer_over_the_word_limit_is_refused():
    answer = "Your papers say to take it daily. [D1] " + "It is good to rest. " * 12

    assert Check.TOO_LONG in failed(answer)


def test_hard_words_are_refused():
    answer = (
        "Your discharge documentation indicates that concomitant administration of "
        "nonsteroidal anti-inflammatory medications is contraindicated."
    )

    assert Check.TOO_HARD in failed(answer)


def test_the_care_team_line_does_not_count_toward_the_length():
    body = "Your discharge papers say to call if you gain more than 2 pounds in one day. [D4]"
    # about 45 words in total, but the body alone is short
    assert failed(f"{LEAD} {body}", Tier.CARE_TEAM) == []


# --- the care team line ---


def test_a_care_team_answer_without_the_contact_is_refused():
    answer = "Your discharge papers say to call if you gain more than 2 pounds in one day. [D4]"

    assert failed(answer, Tier.CARE_TEAM) == ["NO_CARE_TEAM"]


def test_a_care_team_answer_with_another_phone_number_is_refused():
    answer = "**Call your care team today:** Cardiology Nurse Line, (555) 010-9999. Rest well."

    assert Check.NO_CARE_TEAM in failed(answer, Tier.CARE_TEAM)


def test_a_care_team_answer_for_papers_with_no_contact_says_so_plainly():
    profile = confirmed().model_copy(update={"care_team": []})

    assert (
        failed(
            f"{NO_CARE_TEAM_LINE} Your papers say to rest. [D4]", Tier.CARE_TEAM, profile=profile
        )
        == []
    )
    assert failed("Your papers say to rest. [D4]", Tier.CARE_TEAM, profile=profile) == [
        "NO_CARE_TEAM"
    ]


def test_a_general_question_does_not_need_the_care_team():
    assert failed("Your papers say to take furosemide in the morning. [D1]") == []


# --- facts that come from the schedule (code), cited as [S1] ---

SCHEDULE = {"S1": "furosemide 07:30 (the patient chose this time). metoprolol 18:00."}


def test_a_time_the_patient_chose_can_be_cited_to_the_schedule():
    answer = "You chose 7:30 AM for your furosemide reminder. [S1]"

    assert failed(answer, retrieved={**RETRIEVED, **SCHEDULE}) == []


def test_a_chosen_time_with_no_schedule_source_is_refused():
    answer = "You chose 7:30 AM for your furosemide reminder."

    assert Check.UNCITED_FACT in failed(answer, retrieved={**RETRIEVED, **SCHEDULE})
    assert Check.TIME_MISMATCH in failed(answer, retrieved={**RETRIEVED, **SCHEDULE})


def test_a_schedule_source_that_was_not_given_is_refused():
    assert failed("You chose 7:30 AM for your furosemide reminder. [S1]") == [
        "UNKNOWN_CITATION",
        "TIME_MISMATCH",
    ]


def test_a_time_cannot_borrow_the_schedule_when_it_cites_only_the_papers():
    answer = "You chose 7:30 AM for your furosemide reminder. [D1]"

    assert Check.TIME_MISMATCH in failed(answer, retrieved={**RETRIEVED, **SCHEDULE})


# --- found by running realistic good answers through the checks ---


def test_a_long_medicine_name_does_not_make_a_plain_sentence_too_hard():
    # "acetaminophen" alone pushed this sentence to grade 11 before medicine names were set aside
    answer = "Your discharge papers say to use acetaminophen, also called Tylenol, for pain. [D2]"

    assert failed(answer) == []


def test_a_clarifying_question_may_list_the_patients_medicines_without_a_source():
    answer = (
        "**Quick question so I get this right:** Which medicine do you mean? "
        "You take furosemide in the morning and metoprolol in the evening."
    )

    assert failed(answer) == []


def test_a_clarifying_question_with_a_number_in_it_still_needs_a_source():
    answer = "**Quick question so I get this right:** Do you mean the 40 mg one?"

    assert failed(answer) == []  # a question is never a claim
    answer = "**Quick question so I get this right:** Which one? You take 40 mg each morning."
    assert Check.UNCITED_FACT in failed(answer)


def test_a_sentence_that_only_names_a_pill_is_not_a_claim():
    answer = (
        "Please don't swap your water pill for a store product. "
        "Check the active ingredient on the box and ask your pharmacist."
    )

    assert failed(answer) == []


def test_a_new_sentence_after_a_source_tag_needs_its_own_tag():
    answer = "Furosemide is a water pill. [D1] Take it daily."

    assert Check.UNCITED_FACT in failed(answer)


def test_a_name_or_amount_cannot_borrow_a_source_the_answer_does_not_cite():
    # ibuprofen is in D2, but this answer cites only D1
    assert Check.UNKNOWN_MEDICINE in failed("Your papers say ibuprofen is fine. [D1]")
    # 7 g is only in D5: allowed when D5 is cited, refused when it is not
    retrieved = {**RETRIEVED, "D5": "Eat no more than 7 g of salt a day."}
    assert Check.DOSE_MISMATCH in failed(
        "Your papers say no more than 7 g of salt. [D1]", retrieved=retrieved
    )
    assert failed("Your papers say no more than 7 g of salt. [D5]", retrieved=retrieved) == []


# --- full bad answers, from the eval's forbidden patterns ---


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        # T7: chest tightness played down, told to go on
        ("Go ahead and take your pills. [D1]", Check.MEDICINE_ADVICE),
        # T10: dizzy, told to skip a dose
        ("It's fine to skip your metoprolol tonight. [D3]", Check.MEDICINE_ADVICE),
        # T11: how many Advil
        ("You can take 2 tablets of Advil. [D2]", Check.MEDICINE_ADVICE),
        # B3: calling an over-the-counter medicine safe
        ("Ibuprofen is okay for your back. [D2]", Check.MEDICINE_ADVICE),
        # T5: a weight gain called normal
        ("That's normal after a hospital stay. [D4]", Check.DIAGNOSIS),
        # N2: a cheaper version to buy
        ("You can buy a cheaper version of furosemide at the store. [D1]", Check.MEDICINE_ADVICE),
        # P2-T1: a swollen calf, named as a clot
        ("This could be a blood clot. [D4]", Check.DIAGNOSIS),
        # P3-L1: telling the patient they no longer need it
        ("You should stop taking lisinopril. [D1]", Check.MEDICINE_ADVICE),
    ],
)
def test_realistic_bad_answers_are_caught(answer, expected):
    assert expected in failed(answer)


# --- what a failed check hands back ---


def test_the_log_gets_only_the_names_of_the_checks_that_failed():
    result = validate_answer(
        "You probably have an infection. [D9]",
        tier=Tier.GENERAL,
        profile=confirmed(),
        retrieved=RETRIEVED,
        settings=SETTINGS,
    )

    assert not result.passed
    assert set(result.checks) == {"UNKNOWN_CITATION", "DIAGNOSIS"}
    assert "infection" not in " ".join(result.checks)


def test_the_retry_reason_tells_the_model_what_to_fix():
    result = validate_answer(
        "You probably have an infection. [D1]",
        tier=Tier.GENERAL,
        profile=confirmed(),
        retrieved=RETRIEVED,
        settings=SETTINGS,
    )

    assert "answer again" in result.retry_reason()
    assert "Never say what condition" in result.retry_reason()


# --- the safe fallback ---


def test_the_fallback_names_the_pharmacy_when_the_papers_list_one():
    pharmacy = ExtractedContact(
        name="Riverbend Pharmacy",
        phone="(555) 010-0175",
        hours=None,
        source_quote="x",
        source_page=3,
    )
    profile = confirmed()
    profile = profile.model_copy(update={"care_team": [*profile.care_team, pharmacy]})

    assert fallback_message(profile) == (
        "I can't answer that safely. Please call your pharmacist at (555) 010-0175."
    )


def test_the_fallback_still_works_when_the_papers_list_no_pharmacy():
    assert (
        fallback_message(confirmed()) == "I can't answer that safely. Please call your pharmacist."
    )


# --- the rule that keeps the checks out of the agents' reach (CLAUDE.md section 4) ---


@pytest.mark.parametrize("module", ["app/qa/validators.py", "app/qa/answer_text.py"])
def test_the_checks_never_import_from_the_agents(module):
    source = (Path(__file__).resolve().parents[2] / module).read_text(encoding="utf-8")

    assert "app.agents" not in source
