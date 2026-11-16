from app.memory.session import SessionMemory


def test_only_the_last_turns_are_kept():
    memory = SessionMemory(max_turns=2)
    for number in range(3):
        memory.remember("session", "patient", f"q{number}", f"a{number}", None)

    recall = memory.recall("session", "patient")

    assert [turn.question for turn in recall.turns] == ["q1", "q2"]


def test_the_medicine_in_focus_survives_a_question_that_names_none():
    memory = SessionMemory(max_turns=10)
    memory.remember("session", "patient", "what is my water pill", "answer", "furosemide")
    memory.remember("session", "patient", "thanks", "you're welcome", None)

    assert memory.recall("session", "patient").focus_medicine == "furosemide"


def test_a_new_medicine_replaces_the_one_in_focus():
    memory = SessionMemory(max_turns=10)
    memory.remember("session", "patient", "q1", "a1", "furosemide")
    memory.remember("session", "patient", "q2", "a2", "lisinopril")

    assert memory.recall("session", "patient").focus_medicine == "lisinopril"


def test_another_session_or_another_patient_sees_nothing():
    memory = SessionMemory(max_turns=10)
    memory.remember("session-a", "patient-1", "q", "a", "furosemide")

    assert memory.recall("session-b", "patient-1").turns == ()
    assert memory.recall("session-a", "patient-2").turns == ()
    assert memory.recall("session-b", "patient-1").focus_medicine is None


def test_a_conversation_is_forgotten_after_it_sits_idle():
    now = [0.0]
    memory = SessionMemory(max_turns=10, idle_seconds=100, clock=lambda: now[0])
    memory.remember("session", "patient", "q", "a", None)

    now[0] = 99
    assert len(memory.recall("session", "patient").turns) == 1
    now[0] = 99 + 101
    assert memory.recall("session", "patient").turns == ()


def test_forget_drops_every_patient_of_that_session_only():
    memory = SessionMemory(max_turns=10)
    memory.remember("session-a", "patient-1", "q", "a", None)
    memory.remember("session-a", "patient-2", "q", "a", None)
    memory.remember("session-b", "patient-1", "q", "a", None)

    memory.forget("session-a")

    assert memory.recall("session-a", "patient-1").turns == ()
    assert memory.recall("session-a", "patient-2").turns == ()
    assert len(memory.recall("session-b", "patient-1").turns) == 1


def test_the_number_of_conversations_is_capped():
    memory = SessionMemory(max_turns=10, max_conversations=2)
    for number in range(3):
        memory.remember(f"session-{number}", "patient", "q", "a", None)

    assert memory.recall("session-0", "patient").turns == ()
    assert len(memory.recall("session-2", "patient").turns) == 1
