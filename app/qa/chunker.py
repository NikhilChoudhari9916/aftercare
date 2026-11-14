import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.summary.profile import ConfirmedProfile

MAX_CHUNK_CHARS = 700  # about a paragraph; long sections are split at a line
MIN_BODY_CHARS = 20  # a heading with almost nothing under it is not worth a chunk
HEADING_MAX_CHARS = 60
HEADING_MAX_WORDS = 9
BODY_LINE_MIN_CHARS = 40  # a heading is followed by a real sentence, not another label


class PageText(Protocol):
    number: int
    text: str


@dataclass(frozen=True)
class RawChunk:
    page: int
    section: str
    text: str


def chunk_pages(pages: Sequence[PageText]) -> list[RawChunk]:
    """Split the papers by their own section headings, one page at a time.

    Plain text has no font information, so a heading is a short line with a capital letter,
    some lowercase, no closing punctuation, followed by a full sentence. Lines that repeat on
    every page (the hospital header, which holds the patient's name and ID) are dropped.
    """
    repeated = _repeated_lines(pages)
    chunks: list[RawChunk] = []
    for page in pages:
        lines = [line for line in _lines(page.text) if _normal(line) not in repeated]
        chunks.extend(_chunk_page(page.number, lines))
    return chunks


def medicine_chunks(profile: ConfirmedProfile) -> list[RawChunk]:
    """One chunk per confirmed medicine, so a removed medicine can never be searched."""
    chunks = []
    for medicine in profile.medicines:
        name = medicine.name_as_written
        if medicine.other_names:
            name += f" (also known as {', '.join(medicine.other_names)})"
        parts = [name + "."]
        if medicine.dose:
            parts.append(f"Dose: {medicine.dose}.")
        if medicine.frequency or medicine.timing:
            how_often = " ".join(part for part in (medicine.frequency, medicine.timing) if part)
            parts.append(f"How often: {how_often}.")
        parts.append(f"Status: {medicine.status.value.replace('_', ' ')}.")
        if medicine.change_note:
            parts.append(f"What changed: {medicine.change_note}")
        if medicine.end_date:
            parts.append(f"Last day: {medicine.end_date}.")
        parts.append(f'Your papers say: "{medicine.source_quote}"')
        chunks.append(RawChunk(medicine.source_page, "Your medicine list", " ".join(parts)))
    return chunks


def build_chunks(pages: Sequence[PageText], profile: ConfirmedProfile) -> list[RawChunk]:
    return [*chunk_pages(pages), *medicine_chunks(profile)]


def _lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def _normal(line: str) -> str:
    return re.sub(r"\d+", "#", line.casefold())


def _repeated_lines(pages: Sequence[PageText]) -> set[str]:
    """Lines that appear on every page. Only meaningful when there are two pages or more."""
    if len(pages) < 2:
        return set()
    per_page = [{_normal(line) for line in _lines(page.text)} for page in pages]
    return set.intersection(*per_page)


def _is_heading(line: str, next_line: str | None) -> bool:
    return (
        next_line is not None
        and len(next_line) >= BODY_LINE_MIN_CHARS
        and len(line) <= HEADING_MAX_CHARS
        and len(line.split()) <= HEADING_MAX_WORDS
        and line[0].isupper()
        and any(char.islower() for char in line)  # "STOPPED" and "NEW" are labels, not headings
        and not line.endswith((".", ":", ",", ";"))
    )


def _chunk_page(page: int, lines: list[str]) -> list[RawChunk]:
    sections: list[tuple[str, list[str]]] = []
    section = ""
    body: list[str] = []
    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else None
        if _is_heading(line, next_line):
            if body or section:
                sections.append((section, body))
            section, body = line, []
        else:
            body.append(line)
    sections.append((section, body))

    chunks: list[RawChunk] = []
    for name, body_lines in sections:
        if not name and body_lines and len(body_lines[0]) <= HEADING_MAX_CHARS:
            name, body_lines = body_lines[0], body_lines[1:]  # a page that opens with a title
        for piece in _split(body_lines):
            if len(piece) >= MIN_BODY_CHARS:
                chunks.append(RawChunk(page, name or f"Page {page}", piece))
    return chunks


def _split(lines: list[str]) -> list[str]:
    """Join lines into pieces of about MAX_CHUNK_CHARS, breaking only between lines."""
    pieces: list[str] = []
    current = ""
    for line in lines:
        if current and len(current) + len(line) + 1 > MAX_CHUNK_CHARS:
            pieces.append(current)
            current = ""
        current = f"{current} {line}".strip()
    if current:
        pieces.append(current)
    return pieces
