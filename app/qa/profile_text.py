"""The confirmed profile written out as the text the answer prompt's {patient_profile} expects.

The format follows data/synthetic/patient1_profile.txt, which the eval has always used, so the
app shows the model what the eval showed it. Only confirmed items are here, and no name,
age or other identity: the profile does not hold them.
"""

from datetime import date

from app.extraction.schema import ExtractedMedication
from app.summary.profile import ConfirmedProfile

TIER_LABELS = {"CALL_CARE_TEAM": "CALL CARE TEAM", "CALL_911": "CALL 911"}


def _date(day: date) -> str:
    # Not strftime("%-d"): that does not work on Windows.
    return f"{day:%B} {day.day}, {day.year}"


def _status(medicine: ExtractedMedication) -> str:
    word = medicine.status.value.replace("_", " ")
    note = (medicine.change_note or "").strip()
    repeats = note.casefold() in {word.casefold(), medicine.status.value.casefold()}
    return f"{word}: {note}" if note and not repeats else word


def _medicine_line(medicine: ExtractedMedication) -> str:
    parts = [" ".join(part for part in (medicine.name_as_written, medicine.dose) if part)]
    if medicine.other_names:
        parts.append("also known as: " + ", ".join(medicine.other_names))
    how = ", ".join(part for part in (medicine.frequency, medicine.timing) if part)
    if how:
        parts.append(how)
    if medicine.end_date:
        parts.append(f"until {medicine.end_date}")
    parts.append(_status(medicine))
    return " | ".join(parts)


def render_profile_text(profile: ConfirmedProfile) -> str:
    lines = ["Patient profile (confirmed by the patient)"]
    if profile.discharge_date:
        lines.append(f"Discharged: {_date(profile.discharge_date)}")
    lines += ["", "Medicines (confirmed by patient):"]
    if profile.medicines:
        lines += [f"{n}. {_medicine_line(m)}" for n, m in enumerate(profile.medicines, start=1)]
    else:
        lines.append("(none)")

    if profile.follow_ups:
        lines += ["", "Follow-up visits:"]
        for visit in profile.follow_ups:
            who = f" ({visit.with_whom})" if visit.with_whom else ""
            lines.append(f"- {visit.what}: {visit.when}{who}")

    if profile.warning_signs:
        lines += ["", "Warning signs:"]
        for tier, label in TIER_LABELS.items():
            signs = [sign.text for sign in profile.warning_signs if sign.tier == tier]
            if signs:
                lines.append(f"- {label}: " + "; ".join(signs))

    if profile.diet_limits:
        lines += ["", "Diet limits: " + "; ".join(limit.text for limit in profile.diet_limits)]

    if profile.care_team:
        contacts = []
        for contact in profile.care_team:
            hours = f" ({contact.hours})" if contact.hours else ""
            contacts.append(f"{contact.name}, {contact.phone}{hours}")
        lines += ["", "Care team: " + "; ".join(contacts)]
    return "\n".join(lines)
