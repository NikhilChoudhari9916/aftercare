"""The three synthetic patients as confirmed profiles, matching data/synthetic/patientN_profile.txt.

The eval gives the model the text files (as the team's HW2 tests did) and checks the model's
answer with the validators, which need the same facts as typed data. A test keeps the two in step.
"""

from datetime import date

from app.extraction.schema import (
    ExtractedContact,
    ExtractedDietLimit,
    ExtractedFollowUp,
    ExtractedMedication,
    ExtractedWarningSign,
    MedStatus,
)
from app.summary.profile import ConfirmedProfile


def med(
    name, others, dose, frequency, timing, status, quote, *, note=None, end=None, as_needed=False
):
    return ExtractedMedication(
        name_as_written=name,
        other_names=others,
        dose=dose,
        frequency=frequency,
        timing=timing,
        status=status,
        as_needed=as_needed,
        change_note=note,
        end_date=end,
        source_quote=quote,
        source_page=1,
    )


def visit(what, when, with_whom=None):
    return ExtractedFollowUp(
        what=what, when=when, with_whom=with_whom, source_quote=f"{what} {when}", source_page=1
    )


def sign(text, tier):
    return ExtractedWarningSign(text=text, tier=tier, source_quote=text, source_page=1)


def contact(name, phone, hours=None):
    return ExtractedContact(
        name=name, phone=phone, hours=hours, source_quote=f"{name} {phone}", source_page=1
    )


def limit(text):
    return ExtractedDietLimit(text=text, source_quote=text, source_page=1)


def profile(discharged: date, **parts) -> ConfirmedProfile:
    return ConfirmedProfile(
        version_id="eval",
        version=1,
        confirmed_at=None,
        discharge_date=discharged,
        diet_limits=parts.pop("diet_limits", []),
        **parts,
    )


PATIENT1 = profile(
    date(2026, 10, 12),
    medicines=[
        med(
            "furosemide",
            ["Lasix", "water pill"],
            "40 mg",
            "once a day",
            "morning",
            MedStatus.CHANGED,
            "1 tablet by mouth once a day, morning",
            note="Previously 20 mg once daily.",
        ),
        med(
            "metoprolol succinate ER",
            ["Toprol XL"],
            "25 mg",
            "once a day",
            "evening",
            MedStatus.NEW,
            "1 tablet once a day, evening",
        ),
        med(
            "lisinopril",
            ["Zestril", "Prinivil"],
            "10 mg",
            "once a day",
            "morning",
            MedStatus.CONTINUED,
            "1 tablet once a day, morning",
        ),
        med(
            "potassium chloride ER",
            ["Klor-Con", "K-Dur", "potassium"],
            "20 mEq",
            "once a day",
            "with breakfast",
            MedStatus.NEW,
            "1 tablet once a day with breakfast",
        ),
        med(
            "acetaminophen",
            ["Tylenol"],
            "500 mg",
            "1 to 2 tablets every 6 hours as needed for pain; no more than 3,000 mg in 24 hours",
            None,
            MedStatus.AS_NEEDED,
            "1 to 2 tablets every 6 hours as needed for pain; no more than 3,000 mg in 24 hours",
            as_needed=True,
        ),
        med(
            "amlodipine", ["Norvasc"], "5 mg", None, None, MedStatus.STOPPED, "STOPPED: do not take"
        ),
    ],
    warning_signs=[
        sign(
            "weight gain of more than 2 lb in one day or 5 lb in one week; more swelling in legs, "
            "ankles, or feet; dizziness or light-headedness when standing; needing more pillows "
            "to breathe at night",
            "CALL_CARE_TEAM",
        ),
        sign(
            "chest pain; severe shortness of breath; fainting; coughing up pink, foamy mucus",
            "CALL_911",
        ),
    ],
    follow_ups=[
        visit("Blood test (potassium and kidney function)", "October 19, 2026"),
        visit("Cardiology clinic", "October 20, 2026, 10:30 a.m.", "Dr. A. Rivera"),
        visit("Primary care", "within 7 days of discharge"),
    ],
    care_team=[
        contact("Cardiology nurse line", "(555) 010-0142", "weekdays 8 a.m. to 5 p.m."),
        contact("After hours", "(555) 010-0199"),
    ],
    diet_limits=[
        limit("sodium under 2,000 mg a day"),
        limit("fluids under 2 liters (about 8 cups) a day"),
        limit("weigh every morning after using the bathroom and before breakfast"),
    ],
)

PATIENT2 = profile(
    date(2026, 10, 14),
    medicines=[
        med(
            "rivaroxaban",
            ["Xarelto", "blood thinner"],
            "10 mg",
            "once a day",
            "evening",
            MedStatus.NEW,
            "1 tablet once a day, evening, for 12 days (last dose October 26)",
            end="2026-10-26",
        ),
        med(
            "oxycodone",
            ["Roxicodone", "pain pill", "opioid"],
            "5 mg",
            "every 6 hours as needed for severe pain",
            None,
            MedStatus.AS_NEEDED,
            "1 tablet every 6 hours as needed for severe pain",
            as_needed=True,
        ),
        med(
            "acetaminophen",
            ["Tylenol"],
            "500 mg",
            "2 tablets (1,000 mg) every 8 hours; no more than 3,000 mg in 24 hours",
            None,
            MedStatus.NEW,
            "2 tablets (1,000 mg) every 8 hours; no more than 3,000 mg in 24 hours",
        ),
        med(
            "docusate sodium",
            ["Colace", "stool softener"],
            "100 mg",
            "twice a day",
            "while taking oxycodone",
            MedStatus.NEW,
            "1 capsule twice a day while taking oxycodone",
        ),
        med(
            "metformin",
            ["Glucophage"],
            "500 mg",
            "twice a day",
            "with breakfast and dinner",
            MedStatus.CONTINUED,
            "1 tablet twice a day with breakfast and dinner",
        ),
        med(
            "meloxicam",
            ["Mobic"],
            "15 mg",
            None,
            None,
            MedStatus.STOPPED,
            "STOPPED while taking rivaroxaban",
        ),
    ],
    warning_signs=[
        sign(
            "fever over 101°F (38.3°C); redness, warmth, or drainage at the incision; new "
            "or increasing swelling, pain, or warmth in either calf; unusual bruising, nosebleeds, "
            "or bleeding gums; no bowel movement for 3 days",
            "CALL_CARE_TEAM",
        ),
        sign(
            "chest pain or sudden shortness of breath; coughing up blood; signs of stroke; "
            "bleeding that will not stop",
            "CALL_911",
        ),
    ],
    follow_ups=[
        visit("Physical therapy", "starts October 16, 2026, three times a week"),
        visit(
            "Orthopedic surgery (wound check and staple removal)",
            "October 28, 2026, 9:00 a.m.",
            "Dr. K. Osei",
        ),
        visit("Primary care", "within 2 weeks of discharge"),
    ],
    care_team=[
        contact("Orthopedic nurse line", "(555) 010-0233", "weekdays 8 a.m. to 5 p.m."),
        contact("After hours", "(555) 010-0288"),
    ],
    diet_limits=[limit("drink plenty of fluids and eat high-fiber foods while taking oxycodone")],
)

PATIENT3 = profile(
    date(2026, 10, 20),
    medicines=[
        med(
            "furosemide",
            ["Lasix", "water pill"],
            "40 mg",
            "once a day",
            "morning",
            MedStatus.CONTINUED,
            "1 tablet by mouth once a day, morning",
        ),
        med(
            "carvedilol",
            ["Coreg"],
            "6.25 mg",
            "twice a day",
            "with food",
            MedStatus.NEW,
            "1 tablet twice a day with food",
        ),
        med(
            "atorvastatin",
            ["Lipitor"],
            "20 mg",
            "once a day",
            "at bedtime",
            MedStatus.CONTINUED,
            "1 tablet once a day at bedtime",
        ),
    ],
    warning_signs=[
        sign(
            "weight gain of more than 3 lb in two days; more swelling in the legs or feet; "
            "needing more pillows to breathe at night",
            "CALL_CARE_TEAM",
        ),
        sign("chest pain; severe shortness of breath; fainting", "CALL_911"),
    ],
    follow_ups=[visit("Cardiology clinic", "in 1 week", None)],
    care_team=[contact("Cardiology nurse line", "(555) 010-0311", "weekdays 8 a.m. to 5 p.m.")],
    diet_limits=[limit("sodium under 2,000 mg a day")],
)

PROFILES = {"P1": PATIENT1, "P2": PATIENT2, "P3": PATIENT3}
