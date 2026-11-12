import re

from app.extraction.schema import ExtractedProfile

# Case-sensitive on purpose: these are written in capitals on prescriptions.
ABBREVIATIONS = {
    "QAM": "every morning",
    "QPM": "every evening",
    "QHS": "at bedtime",
    "BID": "twice a day",
    "TID": "three times a day",
    "QID": "four times a day",
    "QD": "once a day",
    "PRN": "as needed",
    "PO": "by mouth",
}

_WORD = re.compile(r"(?<![A-Za-z])(" + "|".join(ABBREVIATIONS) + r")(?![A-Za-z])")
_EVERY_N_HOURS = re.compile(r"(?<![A-Za-z])q(\d{1,2})h(?![A-Za-z])", re.IGNORECASE)


def expand_abbreviations(text: str) -> str:
    """Plain code, never the model: 'PO QAM' becomes 'by mouth every morning'."""
    text = _WORD.sub(lambda match: ABBREVIATIONS[match.group(1)], text)
    return _EVERY_N_HOURS.sub(lambda match: f"every {match.group(1)} hours", text)


def normalize_profile(profile: ExtractedProfile) -> ExtractedProfile:
    """Expand abbreviations in the fields the schedule and the patient read."""
    medicines = [
        medicine.model_copy(
            update={
                "frequency": expand_abbreviations(medicine.frequency)
                if medicine.frequency
                else None,
                "timing": expand_abbreviations(medicine.timing) if medicine.timing else None,
            }
        )
        for medicine in profile.medicines
    ]
    return profile.model_copy(update={"medicines": medicines})
