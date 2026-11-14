import re

# Small words that appear in nearly every question and passage, so they say nothing about which
# passage fits. Kept short on purpose: a medicine or body word must never be listed here.
STOP_WORDS = frozenset(
    """a an the and or but if so is are was were be been am do does did have has had i me my we
    you your it its this that these those to of for in on at by from with as can could should
    would will what when where which who why how about any some more than then there here not
    no yes also just very really still now""".split()
)


def tokens(text: str) -> list[str]:
    """Lowercase words, without filler words, with a plural "s" removed ("pills" -> "pill")."""
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return [_singular(word) for word in words if word not in STOP_WORDS]


def _singular(word: str) -> str:
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word
