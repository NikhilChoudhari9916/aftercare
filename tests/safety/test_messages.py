from app.safety.messages import NO_CARE_TEAM_LINE, TIER1_MESSAGE, care_team_line


def test_the_emergency_text_is_exactly_the_one_in_the_project_rules():
    # Copied from CLAUDE.md section 5. If this test needs to change, the team decides first.
    assert TIER1_MESSAGE == (
        "This could be an emergency. Please call 911 now. "
        "Do not drive yourself. If someone is with you, ask them to stay with you."
    )


def test_the_care_team_line_names_who_to_call_from_the_papers():
    assert (
        care_team_line("Cardiology Nurse Line", "(555) 010-0142", "weekdays 8 a.m. to 5 p.m.")
        == "Please call Cardiology Nurse Line at (555) 010-0142 (weekdays 8 a.m. to 5 p.m.)."
    )
    assert (
        care_team_line("Nurse line", "(555) 010-0233")
        == "Please call Nurse line at (555) 010-0233."
    )


def test_without_a_contact_the_line_still_says_who_to_ask():
    assert care_team_line(None, None) == NO_CARE_TEAM_LINE
    assert care_team_line("Nurse line", "") == NO_CARE_TEAM_LINE
