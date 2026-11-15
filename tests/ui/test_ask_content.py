from pathlib import Path

from ui.api_client import Citation
from ui.content import EMERGENCY_BANNER, answer_html, citation_labels

PAPER = Citation(id="D1", kind="paper", page=1, label="From your papers, page 1")
LABEL = Citation(id="L1", kind="label", label="From the drug label")


def test_a_source_tag_becomes_its_plain_label():
    html = answer_html("Take it in the morning. [D1]", citation_labels([PAPER]))

    assert "From your papers, page 1" in html
    assert "[D1]" not in html


def test_a_tag_with_no_known_label_is_dropped_so_a_code_is_never_shown():
    html = answer_html("Take it in the morning. [D7]", citation_labels([PAPER]))

    assert "D7" not in html


def test_bold_marks_become_bold_text():
    assert "<b>40 mg</b>" in answer_html("Take **40 mg** daily. [D1]", citation_labels([PAPER]))


def test_nothing_the_model_wrote_can_become_html():
    html = answer_html('<script>alert("x")</script> [D1] <img src=x onerror=y>', {"D1": "<b>x</b>"})

    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html
    assert "<b>x</b>" not in html  # even a label is escaped


def test_new_lines_stay_new_lines():
    assert "one<br>two" in answer_html("one\ntwo", {})


def test_labels_are_looked_up_by_id():
    assert citation_labels([PAPER, LABEL]) == {
        "D1": "From your papers, page 1",
        "L1": "From the drug label",
    }


def test_the_not_confirmed_screen_carries_the_same_911_line_as_the_ask_page():
    layout = Path(__file__).resolve().parents[2] / "ui" / "layout.py"

    assert EMERGENCY_BANNER in layout.read_text(encoding="utf-8")
