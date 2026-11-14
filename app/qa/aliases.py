import re


def expand_query(question: str, name_groups: list[list[str]]) -> str:
    """Add a medicine's other names to a question that names it.

    "did they change the lasix" also searches "furosemide", which is the word the papers use.
    `name_groups` holds one list per confirmed medicine: its name and its other names.
    """
    asked = question.casefold()
    extra: list[str] = []
    for names in name_groups:
        if any(_mentions(asked, name) for name in names):
            extra.extend(name for name in names if not _mentions(asked, name))
    return " ".join([question, *extra]) if extra else question


def _mentions(text: str, name: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(name.casefold())}(?![a-z0-9])", text) is not None
