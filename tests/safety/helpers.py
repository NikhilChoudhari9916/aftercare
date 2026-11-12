from app.llm import LLMResponse
from app.safety.context import CareContact, PatientSafetyContext, ProfileWarningSign, safety_context
from tests.fakes import FakeLLM
from tests.summary.helpers import confirmed


def reply(text: str) -> LLMResponse:
    return LLMResponse(text=text, tool_calls=[], stop_reason="end_turn", content=[])


def llm_saying(*texts: str) -> FakeLLM:
    llm = FakeLLM()
    for text in texts:
        llm.queue_reply(reply(text))
    return llm


def patient1() -> PatientSafetyContext:
    return safety_context(confirmed())


def patient2() -> PatientSafetyContext:
    """Patient 2 (knee replacement), written by hand from data/synthetic/patient2_profile.txt."""
    return PatientSafetyContext(
        warning_signs=[
            ProfileWarningSign(text="fever over 101°F (38.3°C)", tier="CALL_CARE_TEAM"),
            ProfileWarningSign(
                text="redness, warmth, or drainage at the incision", tier="CALL_CARE_TEAM"
            ),
            ProfileWarningSign(
                text="new or increasing swelling, pain, or warmth in either calf",
                tier="CALL_CARE_TEAM",
            ),
            ProfileWarningSign(
                text="unusual bruising, nosebleeds, or bleeding gums", tier="CALL_CARE_TEAM"
            ),
            ProfileWarningSign(text="no bowel movement for 3 days", tier="CALL_CARE_TEAM"),
            ProfileWarningSign(text="chest pain or sudden shortness of breath", tier="CALL_911"),
            ProfileWarningSign(text="coughing up blood", tier="CALL_911"),
            ProfileWarningSign(text="signs of stroke", tier="CALL_911"),
            ProfileWarningSign(text="bleeding that will not stop", tier="CALL_911"),
        ],
        medicine_names=[
            "rivaroxaban",
            "xarelto",
            "oxycodone",
            "roxicodone",
            "acetaminophen",
            "tylenol",
            "docusate",
            "colace",
            "metformin",
            "glucophage",
            "meloxicam",
            "mobic",
        ],
        care_team=[
            CareContact(
                name="Orthopedic nurse line",
                phone="(555) 010-0233",
                hours="weekdays 8 a.m. to 5 p.m.",
            )
        ],
    )


def patient3() -> PatientSafetyContext:
    return PatientSafetyContext(medicine_names=["lisinopril", "prinivil", "zestril"])


CONTEXTS = {"P1": patient1, "P2": patient2, "P3": patient3}
