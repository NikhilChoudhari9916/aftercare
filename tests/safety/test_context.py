from app.safety.context import safety_context
from tests.summary.helpers import confirmed


def test_the_context_holds_only_plain_confirmed_data():
    context = safety_context(confirmed())

    assert {"furosemide", "lasix", "metoprolol", "toprol", "lisinopril"} <= set(
        context.medicine_names
    )
    assert [sign.tier for sign in context.warning_signs] == ["CALL_CARE_TEAM", "CALL_911"]
    assert context.care_team[0].phone == "(555) 010-0142"


def test_very_short_names_are_left_out_so_they_cannot_match_inside_other_words():
    short = (
        confirmed()
        .medicines[0]
        .model_copy(update={"name_as_written": "iron", "other_names": ["Fe"]})
    )
    context = safety_context(confirmed(medicines=[short]))

    assert "fe" not in context.medicine_names
    assert "iron" in context.medicine_names
