import pytest

from app.extraction.abbreviations import expand_abbreviations, normalize_profile
from tests.samples import patient1_profile


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("40 mg PO QAM", "40 mg by mouth every morning"),
        ("25 mg PO QPM", "25 mg by mouth every evening"),
        ("500-1,000 mg PO q6h PRN pain", "500-1,000 mg by mouth every 6 hours as needed pain"),
        ("1 tablet BID", "1 tablet twice a day"),
        ("TID with meals", "three times a day with meals"),
        ("QHS", "at bedtime"),
        ("take Q12H", "take every 12 hours"),
    ],
)
def test_prescription_shorthand_becomes_plain_words(written, expected):
    assert expand_abbreviations(written) == expected


@pytest.mark.parametrize(
    "text",
    ["POTASSIUM chloride", "Bidirectional", "the po box", "SPOT check", "QUIT smoking"],
)
def test_letters_inside_other_words_and_lowercase_text_are_left_alone(text):
    assert expand_abbreviations(text) == text


def test_normalizing_a_profile_expands_frequency_but_never_touches_the_source_quote():
    profile = patient1_profile()
    medicines = list(profile.medicines)
    medicines[0] = medicines[0].model_copy(
        update={"frequency": "once daily PO QAM", "source_quote": "Sig: 40 mg PO QAM"}
    )
    profile = profile.model_copy(update={"medicines": medicines})

    cleaned = normalize_profile(profile)

    assert cleaned.medicines[0].frequency == "once daily by mouth every morning"
    assert cleaned.medicines[0].source_quote == "Sig: 40 mg PO QAM"
    assert cleaned.medicines[5].frequency is None
