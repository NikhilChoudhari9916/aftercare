"""Resolve a medicine reference from explicit user context, without adding medical knowledge."""

import re

from app.memory.session import Recall
from app.summary.profile import ConfirmedProfile

REFERENCE = re.compile(r"\b(it|that (?:medicine|pill|one)|this (?:medicine|pill))\b", re.IGNORECASE)


def named_medicines(profile: ConfirmedProfile, question: str) -> list[str]:
    found = []
    for medicine in profile.medicines:
        names = [medicine.name_as_written, *medicine.other_names]
        # A unique first word, such as metoprolol, is already part of the confirmed name.
        names.append(
            medicine.name_as_written.split()[0] if medicine.name_as_written.split() else ""
        )
        if any(
            name
            and re.search(
                rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", question, re.IGNORECASE
            )
            for name in names
        ):
            found.append(medicine.name_as_written)
    return found


def resolve_reference(
    profile: ConfirmedProfile, question: str, recall: Recall
) -> tuple[str, str | None]:
    explicit = named_medicines(profile, question)
    if explicit:
        return question, explicit[0] if len(explicit) == 1 else None
    if not REFERENCE.search(question) or not recall.turns:
        return question, None
    last = recall.turns[-1]
    previous = named_medicines(profile, last.question)
    # A successful pronoun turn carries a code-resolved identity, not medical evidence.
    if (
        not previous
        and REFERENCE.search(last.question)
        and last.focus_medicine in {m.name_as_written for m in profile.medicines}
    ):
        previous = [last.focus_medicine]
    if len(previous) != 1:
        # Do not carry a stale focus across an unrelated turn or guess between two medicines.
        return question, None
    return REFERENCE.sub(lambda _match: previous[0], question), previous[0]
