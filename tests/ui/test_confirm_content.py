from ui.content import (
    CONFIRMED_NEXT,
    EDIT_FIELDS,
    MEDICINE_FIX_TITLE,
    MEDICINE_FIX_WARNING,
    MISSING_FACT,
    VISIT_CONFIRM_NOTE,
    medicine_facts,
    needs_close_look,
)


def test_the_two_facts_that_must_be_right_are_shown_as_the_papers_say_them():
    data = {"dose": "40 mg", "frequency": "once daily", "timing": "in the morning"}
    assert medicine_facts(data) == [
        ("Dose", "40 mg", False),
        ("How often", "once daily in the morning", False),
    ]


def test_a_missing_dose_or_frequency_is_marked_so_the_patient_notices_the_gap():
    facts = medicine_facts({"dose": None, "frequency": None, "timing": None})
    assert facts == [("Dose", MISSING_FACT, True), ("How often", MISSING_FACT, True)]


def test_a_stopped_medicine_without_a_schedule_is_not_flagged_as_a_gap():
    data = {"dose": "5 mg", "frequency": None, "timing": None, "status": "STOPPED"}
    assert medicine_facts(data)[1] == ("How often", "Stopped, no schedule", False)
    # but a missing dose is still a gap, and so is a missing schedule on a medicine in use
    assert medicine_facts({**data, "dose": None})[0] == ("Dose", MISSING_FACT, True)
    assert medicine_facts({**data, "status": "CONTINUED"})[1] == ("How often", MISSING_FACT, True)


def test_only_the_timing_words_are_missing_when_the_frequency_is_there():
    facts = medicine_facts({"dose": "5 mg", "frequency": "twice a day", "timing": None})
    assert facts[1] == ("How often", "twice a day", False)


def test_a_line_at_the_top_counts_items_whose_words_could_not_be_found():
    assert needs_close_look(["verified", "verified"]) is None
    assert needs_close_look([]) is None
    one = needs_close_look(["verified", "not_found"])
    assert one.startswith("1 item needs a close look")
    many = needs_close_look(["not_found", "not_found", "verified"])
    assert many.startswith("2 items need a close look")


def test_the_time_of_day_choice_is_no_longer_a_box_on_the_check_screen():
    labels = [label for _, label in EDIT_FIELDS["medicines"]]
    assert not any("time of day" in label.lower() for label in labels)
    assert any("papers" in label.lower() for label in labels)  # only the papers' own wording


def test_changing_a_medicine_is_framed_as_a_mismatch_with_the_papers():
    assert "doesn't match" in MEDICINE_FIX_TITLE
    assert "only change this if your papers say something different" in MEDICINE_FIX_WARNING.lower()
    assert "reminder times" in MEDICINE_FIX_WARNING


def test_visits_are_confirmed_as_words_and_planned_next():
    assert "words only" in VISIT_CONFIRM_NOTE
    assert "reminders" in CONFIRMED_NEXT or "plan" in CONFIRMED_NEXT
