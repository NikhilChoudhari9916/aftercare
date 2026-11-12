import re
from dataclasses import dataclass

from app.ingestion.pdf_reader import PdfPage

# Text in a document that talks to an AI instead of to the patient (ADR-0031). The document
# is data, so these never change behavior; they are only shown to the patient as a warning.
PATTERNS = {
    "ignore_rules": re.compile(
        r"(ignore|disregard|forget)\s+(all\s+|any\s+|your\s+|the\s+|these\s+)*"
        r"(previous\s+|prior\s+|above\s+|earlier\s+)*(rules|instructions|prompts?|guidelines)",
        re.IGNORECASE,
    ),
    "role_change": re.compile(
        r"(you are now|act as|pretend to be|from now on you)\b.{0,40}"
        r"\b(ai|assistant|chatbot|model|doctor)\b",
        re.IGNORECASE,
    ),
    "reveal_prompt": re.compile(
        r"(reveal|show|print|repeat)\s+(your|the)\s+(system\s+)?(prompt|rules|instructions)",
        re.IGNORECASE,
    ),
    "stop_medicines": re.compile(
        r"stop\s+(taking\s+)?all\s+(of\s+)?(your\s+|the\s+)?medic", re.IGNORECASE
    ),
    "hide_from_patient": re.compile(
        r"do not (tell|inform|show)\s+the\s+(user|patient)", re.IGNORECASE
    ),
}


@dataclass(frozen=True)
class InjectionFlag:
    page: int
    kind: str
    excerpt: str


def scan_for_instructions(pages: list[PdfPage]) -> list[InjectionFlag]:
    flags = []
    for page in pages:
        for line in page.text.splitlines():
            for kind, pattern in PATTERNS.items():
                if pattern.search(line):
                    flags.append(InjectionFlag(page.number, kind, line.strip()[:160]))
    return flags
