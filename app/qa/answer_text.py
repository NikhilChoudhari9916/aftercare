import re
from dataclasses import dataclass

# D: the patient's papers, L: an FDA label, T: a MedlinePlus term, S: the schedule (built by code
# from the papers and the patient's own reminder choices, so "you chose 7:30 AM" has a source).
CITATION = re.compile(r"\[([DLTS]\d+)\]")
_ANALYSIS = re.compile(r"<analysis>.*?(?:</analysis>|\Z)", re.DOTALL | re.IGNORECASE)
_FOLLOWUPS = re.compile(r"<followups>(.*?)(?:</followups>|\Z)", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class ParsedAnswer:
    visible: str  # what the patient reads, with bold marks and [D1] tags still in it
    followups: list[str]  # the buttons, from the <followups> block


def parse_answer(raw: str) -> ParsedAnswer:
    """Split a model reply into what the patient sees and the follow-up buttons.

    The hidden <analysis> is dropped here and never kept: it can hold patient text (ADR-0031).
    An <analysis> that is never closed drops everything after it, so a cut-off reply fails the
    "empty answer" check and is never shown.
    """
    without_analysis = _ANALYSIS.sub("", raw)
    followups = [
        line.strip().removeprefix("-").strip()
        for block in _FOLLOWUPS.findall(without_analysis)
        for line in block.splitlines()
        if line.strip().startswith("-")
    ]
    visible = _FOLLOWUPS.sub("", without_analysis).strip()
    return ParsedAnswer(visible=visible, followups=[f for f in followups if f])


def cited_ids(text: str) -> list[str]:
    """Every source ID in the text, in order, such as ["D1", "L2"]."""
    return CITATION.findall(text)


def plain_text(visible: str) -> str:
    """The answer as a person reads it: no source tags, no bold marks, one space between words."""
    text = CITATION.sub("", visible).replace("**", "")
    # "a.m." and "Dr." would otherwise look like the end of a sentence.
    text = re.sub(r"\b([ap])\.m\.", r"\1m", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(Dr|Mr|Mrs|Ms|St)\.", r"\1", text)
    return " ".join(text.split())
