import pytest

from app.memory.session import Recall, Turn
from app.qa.references import resolve_reference
from tests.summary.helpers import confirmed


def test_it_resolves_to_the_medicine_in_the_immediately_preceding_user_turn():
    recall = Recall(turns=(Turn("What is furosemide also called?", "Invented explanation"),))
    text, focus = resolve_reference(confirmed(), "When do my papers say to take it?", recall)
    assert text == "When do my papers say to take furosemide?"
    assert focus == "furosemide"


@pytest.mark.parametrize(
    "previous",
    ["What are furosemide and lisinopril for?", "When is my visit?", "What are all my medicines?"],
)
def test_an_ambiguous_or_unrelated_turn_does_not_reuse_a_stale_focus(previous):
    recall = Recall(turns=(Turn(previous, "answer"),), focus_medicine="furosemide")
    text, focus = resolve_reference(confirmed(), "When do I take it?", recall)
    assert text == "When do I take it?" and focus is None


def test_explicit_medicine_overrides_previous_context_and_preserves_symptoms():
    recall = Recall(turns=(Turn("What is furosemide?", "answer"),))
    text, focus = resolve_reference(confirmed(), "I feel dizzy after metoprolol", recall)
    assert text == "I feel dizzy after metoprolol" and focus == "metoprolol succinate ER"


def test_model_generated_memory_is_not_used_to_invent_a_medicine_reference():
    recall = Recall(turns=(Turn("Hello", "You mean furosemide"),), focus_medicine="furosemide")
    assert resolve_reference(confirmed(), "When do I take it?", recall) == (
        "When do I take it?",
        None,
    )


def test_a_verified_reference_can_continue_for_another_turn_without_using_answer_facts():
    from app.memory.session import SessionMemory

    memory = SessionMemory(max_turns=10)
    memory.remember(
        "session", "patient", "When do I take it?", "Untrusted generated prose", "furosemide"
    )
    text, focus = resolve_reference(
        confirmed(), "What dose of it is listed?", memory.recall("session", "patient")
    )
    assert text == "What dose of furosemide is listed?" and focus == "furosemide"
    assert resolve_reference(
        confirmed(), "When do I take it?", memory.recall("other", "patient")
    ) == ("When do I take it?", None)
