from app.qa.answer_text import cited_ids, parse_answer, plain_text


def test_the_hidden_analysis_never_reaches_the_patient():
    raw = "<analysis>Step 1: she said her chest hurts</analysis>\nTake it in the morning. [D1]"

    assert parse_answer(raw).visible == "Take it in the morning. [D1]"


def test_follow_up_questions_become_buttons_and_leave_the_answer():
    raw = (
        "Take it in the morning. [D1]\n<followups>\n- What if I miss a dose?\n"
        "- Can I take it with food?\n</followups>"
    )

    parsed = parse_answer(raw)

    assert parsed.visible == "Take it in the morning. [D1]"
    assert parsed.followups == ["What if I miss a dose?", "Can I take it with food?"]


def test_an_analysis_that_is_never_closed_swallows_the_rest_so_it_cannot_leak():
    parsed = parse_answer("<analysis>Step 1: private thoughts\nTake it daily. [D1]")

    assert parsed.visible == ""


def test_a_reply_with_no_tags_is_all_visible():
    assert parse_answer("Your papers say so. [D1]").visible == "Your papers say so. [D1]"
    assert parse_answer("Your papers say so. [D1]").followups == []


def test_source_ids_are_listed_in_order():
    assert cited_ids("One. [D2] Two. [L1] Three. [T3] [D2]") == ["D2", "L1", "T3", "D2"]
    assert cited_ids("No tags, but [brackets] and [X1].") == []


def test_plain_text_is_what_a_person_reads():
    visible = "**Call your care team today:** Dr. Chen, 8 a.m. to 5 p.m. [D3]"

    assert plain_text(visible) == "Call your care team today: Dr Chen, 8 am to 5 pm"
