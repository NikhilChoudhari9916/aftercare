from ui.api_client import Me, PatientRef, UserInfo
from ui.components.shell import _initial, _links


def person(*roles: str, name: str = "Ada Lovelace") -> Me:
    return Me(
        user=UserInfo(id="u1", email="ada@example.com", display_name=name),
        patients=[PatientRef(id=f"p{index}", role=role) for index, role in enumerate(roles)],
    )


def test_nobody_signed_in_sees_only_the_how_it_works_link():
    assert _links(None) == [("How it works", "#how")]


def test_a_patient_gets_every_page():
    assert [text for text, _ in _links(person("OWNER"))] == [
        "Home",
        "Upload",
        "Review",
        "Summary",
        "Schedule",
    ]
    assert [target for _, target in _links(person("OWNER"))] == [
        "/",
        "/upload",
        "/confirm",
        "/summary",
        "/schedule",
    ]


def test_an_aide_sees_only_the_pages_an_aide_may_read():
    assert _links(person("AIDE")) == [
        ("Home", "/"),
        ("Summary", "/summary"),
        ("Schedule", "/schedule"),
    ]


def test_the_avatar_shows_the_first_letter_in_capitals():
    assert _initial(person("OWNER", name="ada lovelace")) == "A"
    assert _initial(person("OWNER", name="   ")) == "?"
