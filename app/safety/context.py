from typing import Literal

from pydantic import BaseModel

from app.summary.profile import ConfirmedProfile

# Medicine names shorter than this would match inside ordinary words, so they are not used.
MIN_MEDICINE_NAME_LENGTH = 4


class ProfileWarningSign(BaseModel):
    text: str
    tier: Literal["CALL_911", "CALL_CARE_TEAM"]


class CareContact(BaseModel):
    name: str
    phone: str
    hours: str | None = None


class PatientSafetyContext(BaseModel):
    """What the gate knows about this patient: only confirmed items, and plain data.

    The gate never sees the profile object itself, so nothing in the safety path can write to it.
    """

    warning_signs: list[ProfileWarningSign] = []
    medicine_names: list[str] = []
    care_team: list[CareContact] = []


def safety_context(profile: ConfirmedProfile) -> PatientSafetyContext:
    names: list[str] = []
    for medicine in profile.medicines:
        for name in (medicine.name_as_written, *medicine.other_names):
            # The first word too: "metoprolol succinate ER" is usually just called "metoprolol".
            words = name.strip().lower().split()
            for candidate in (" ".join(words), words[0] if words else ""):
                if len(candidate) >= MIN_MEDICINE_NAME_LENGTH and candidate not in names:
                    names.append(candidate)
    return PatientSafetyContext(
        warning_signs=[
            ProfileWarningSign(text=sign.text, tier=sign.tier) for sign in profile.warning_signs
        ],
        medicine_names=names,
        care_team=[
            CareContact(name=contact.name, phone=contact.phone, hours=contact.hours)
            for contact in profile.care_team
        ],
    )
