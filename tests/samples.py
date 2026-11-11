from pathlib import Path

from app.extraction.schema import (
    ExtractedContact,
    ExtractedDietLimit,
    ExtractedFollowUp,
    ExtractedMedication,
    ExtractedProfile,
    ExtractedWarningSign,
    MedStatus,
)

PATIENT1_PDF = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "synthetic"
    / ("patient1_discharge_summary.pdf")
)


def medicine(name, other, dose, frequency, status, quote, *, as_needed=False, note=None, page=1):
    return ExtractedMedication(
        name_as_written=name,
        other_names=other,
        dose=dose,
        frequency=frequency,
        timing=None,
        status=status,
        as_needed=as_needed,
        change_note=note,
        end_date=None,
        source_quote=quote,
        source_page=page,
    )


def patient1_profile() -> ExtractedProfile:
    """What a good extraction of the synthetic Patient 1 PDF looks like. Every quote is real."""
    return ExtractedProfile(
        discharge_date="2026-10-12",
        medicines=[
            medicine(
                "furosemide",
                ["LASIX"],
                "40 mg",
                "once daily in the morning",
                MedStatus.CHANGED,
                "Take 1 tablet (40 mg) by mouth once daily in the morning.",
                note="Previously 20 mg once daily.",
            ),
            medicine(
                "metoprolol succinate ER",
                ["TOPROL XL"],
                "25 mg",
                "once daily in the evening",
                MedStatus.NEW,
                "Take 1 tablet by mouth once daily in the evening.",
            ),
            medicine(
                "potassium chloride ER",
                ["KLOR-CON"],
                "20 mEq",
                "once daily with breakfast",
                MedStatus.NEW,
                "Take 1 tablet by mouth once daily with breakfast",
            ),
            medicine(
                "lisinopril",
                ["ZESTRIL"],
                "10 mg",
                "once daily in the morning",
                MedStatus.CONTINUED,
                "CONTINUE: no change",
            ),
            medicine(
                "acetaminophen",
                ["TYLENOL"],
                "500 mg",
                "every 6 hours as needed",
                MedStatus.AS_NEEDED,
                "Take 1 to 2 tablets by mouth every 6 hours as needed for pain.",
                as_needed=True,
            ),
            medicine(
                "amlodipine",
                ["NORVASC"],
                "5 mg",
                None,
                MedStatus.STOPPED,
                "STOP taking this medicine.",
            ),
        ],
        warning_signs=[
            ExtractedWarningSign(
                text="Gain more than 2 pounds in one day or 5 pounds in one week",
                tier="CALL_CARE_TEAM",
                source_quote="gain more than 2 pounds in one day or 5 pounds in one week",
                source_page=2,
            ),
            ExtractedWarningSign(
                text="Chest pain, severe shortness of breath, fainting, or coughing up pink, "
                "foamy mucus",
                tier="CALL_911",
                source_quote=(
                    "CALL 911 for chest pain, severe shortness of breath, fainting, "
                    "or coughing up pink, foamy mucus."
                ),
                source_page=2,
            ),
        ],
        follow_ups=[
            ExtractedFollowUp(
                what="Cardiology follow-up",
                when="Tuesday, 10/20/2026 at 10:30 a.m.",
                with_whom="A. Rivera, MD",
                source_quote="Cardiology follow-up Tuesday, 10/20/2026 at 10:30",
                source_page=3,
            )
        ],
        care_team=[
            ExtractedContact(
                name="Cardiology Nurse Line",
                phone="(555) 010-0142",
                hours="Monday to Friday, 8 a.m. to 5 p.m.",
                source_quote="Cardiology Nurse Line (weekdays 8 a.m. to 5 p.m.) (555) 010-0142",
                source_page=3,
            )
        ],
        diet_limits=[
            ExtractedDietLimit(
                text="Limit sodium to less than 2,000 mg per day",
                source_quote="Limit sodium to less than 2,000 mg per day.",
                source_page=2,
            )
        ],
    )


def make_pdf(*page_texts: str) -> bytes:
    """A tiny real PDF with the given text on each page."""
    import pymupdf

    document = pymupdf.open()
    for text in page_texts:
        document.new_page().insert_text((72, 72), text)
    return document.tobytes()
