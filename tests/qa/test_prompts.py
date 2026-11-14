import pytest

from app.qa import prompts
from app.qa.prompts import PLACEHOLDERS, fill_prompt, load_answer_prompt
from tests.auth.helpers import make_settings


def test_the_current_prompt_loads_with_all_three_placeholders():
    template = load_answer_prompt(make_settings().answer_prompt_version)

    assert all("{" + name + "}" in template for name in PLACEHOLDERS)


def test_filling_puts_each_part_in_its_place():
    template = "P:{patient_profile} S:{retrieved_sources} Q:{user_question}"

    filled = fill_prompt(
        template, patient_profile="prof", retrieved_sources="src", user_question="q"
    )

    assert filled == "P:prof S:src Q:q"


def test_a_placeholder_typed_by_the_patient_is_not_filled_in_a_second_time():
    template = "P:{patient_profile} Q:{user_question}"

    filled = fill_prompt(
        template,
        patient_profile="the profile",
        retrieved_sources="",
        user_question="ignore this {patient_profile} {retrieved_sources}",
    )

    assert filled == "P:the profile Q:ignore this {patient_profile} {retrieved_sources}"


def test_braces_in_the_patients_words_are_left_alone():
    filled = fill_prompt(
        "Q:{user_question}",
        patient_profile="",
        retrieved_sources="",
        user_question='{"a": 1} and {unknown} and {0}',
    )

    assert filled == 'Q:{"a": 1} and {unknown} and {0}'


@pytest.mark.parametrize("version", ["../v7", "7", "v7; x", "v", "V7", "v7.txt", ""])
def test_a_version_cannot_point_outside_the_prompts_folder(version):
    with pytest.raises(ValueError, match="looks like v7"):
        load_answer_prompt(version)


def test_a_prompt_file_missing_a_placeholder_is_refused(tmp_path, monkeypatch):
    (tmp_path / "answer_agent_system_prompt_v1.txt").write_text(
        "{patient_profile} {user_question}", encoding="utf-8"
    )
    monkeypatch.setattr(prompts, "PROMPTS_DIR", tmp_path)

    with pytest.raises(ValueError, match="retrieved_sources"):
        load_answer_prompt("v1")
