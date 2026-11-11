from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class MedStatus(StrEnum):
    NEW = "NEW"
    CHANGED = "CHANGED"
    STOPPED = "STOPPED"
    CONTINUED = "CONTINUED"
    AS_NEEDED = "AS_NEEDED"


class Sourced(BaseModel):
    """Every extracted fact points back to the exact words it came from."""

    source_quote: str = Field(description="Exact words copied from the document")
    source_page: int = Field(description="Page number from the page marker, starting at 1")


class ExtractedMedication(Sourced):
    name_as_written: str = Field(description="Generic name as the document writes it")
    other_names: list[str] = Field(description="Brand names or other names written for it")
    dose: str | None = Field(description="Strength as written, such as 40 mg")
    frequency: str | None = Field(description="How often, as the document writes it")
    timing: str | None = Field(description="Time of day or with food, if the document says")
    status: MedStatus
    as_needed: bool = Field(description="True if taken only when needed")
    change_note: str | None = Field(description="The document's own words about what changed")
    end_date: str | None = Field(description="YYYY-MM-DD only if the document states it")


class ExtractedWarningSign(Sourced):
    text: str
    tier: Literal["CALL_911", "CALL_CARE_TEAM"]


class ExtractedFollowUp(Sourced):
    what: str
    when: str = Field(description="When, as the document writes it")
    with_whom: str | None


class ExtractedContact(Sourced):
    name: str
    phone: str
    hours: str | None


class ExtractedDietLimit(Sourced):
    text: str


class ExtractedProfile(BaseModel):
    discharge_date: str | None = Field(description="YYYY-MM-DD if the document states it")
    medicines: list[ExtractedMedication]
    warning_signs: list[ExtractedWarningSign]
    follow_ups: list[ExtractedFollowUp]
    care_team: list[ExtractedContact]
    diet_limits: list[ExtractedDietLimit]


SECTION_MODELS: dict[str, type[Sourced]] = {
    "medicines": ExtractedMedication,
    "warning_signs": ExtractedWarningSign,
    "follow_ups": ExtractedFollowUp,
    "care_team": ExtractedContact,
    "diet_limits": ExtractedDietLimit,
}
SOURCED_SECTIONS = tuple(SECTION_MODELS)
