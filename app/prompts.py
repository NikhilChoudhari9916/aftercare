from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache
def load_prompt(name: str) -> str:
    """Prompts are files, never strings in code (CLAUDE.md section 16)."""
    if Path(name).name != name:
        raise ValueError("prompt names are plain file names")
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")
