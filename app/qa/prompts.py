import re

from app.config import PROMPTS_DIR

PLACEHOLDERS = ("patient_profile", "retrieved_sources", "user_question")
_PLACEHOLDER = re.compile(r"\{(" + "|".join(PLACEHOLDERS) + r")\}")
_VERSION = re.compile(r"v\d+")


def load_answer_prompt(version: str) -> str:
    """The answer prompt template for one version, such as "v7". Prompts are files, never code."""
    if not _VERSION.fullmatch(version):
        raise ValueError("A prompt version looks like v7")
    text = (PROMPTS_DIR / f"answer_agent_system_prompt_{version}.txt").read_text(encoding="utf-8")
    missing = [name for name in PLACEHOLDERS if "{" + name + "}" not in text]
    if missing:
        raise ValueError(f"The prompt is missing its placeholders: {', '.join(missing)}")
    return text


def fill_prompt(
    template: str, *, patient_profile: str, retrieved_sources: str, user_question: str
) -> str:
    """Put the patient's profile, the sources and the question into the template.

    One pass, so a placeholder written inside the patient's own words is not filled in again,
    and braces in their text are left alone (which `str.format` would not do).
    """
    values = {
        "patient_profile": patient_profile,
        "retrieved_sources": retrieved_sources,
        "user_question": user_question,
    }
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], template)
