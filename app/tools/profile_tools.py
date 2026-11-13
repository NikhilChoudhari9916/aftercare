from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.extraction.schema import ExtractedMedication
from app.summary.plan import load_plan
from app.summary.profile import ConfirmedProfile, load_confirmed_profile
from app.summary.schedule import DoseTime, FollowUpLine, MedicineLine, build_schedule
from app.tools.registry import NoInput, Tool, ToolContext, ToolError

MAX_PASSAGES = 4  # CLAUDE.md section 15: keep the top 4 chunks


def confirmed_profile(context: ToolContext) -> ConfirmedProfile:
    """The patient's confirmed papers. Nothing unconfirmed is ever used in an answer."""
    profile = load_confirmed_profile(context.db, context.patient_id)
    if profile is None:
        raise ToolError("The papers have not been confirmed yet.")
    return profile


# --- get_confirmed_medicines ---


class ConfirmedMedicines(BaseModel):
    medicines: list[ExtractedMedication]


def _get_confirmed_medicines(context: ToolContext, _arguments: NoInput) -> ConfirmedMedicines:
    return ConfirmedMedicines(medicines=confirmed_profile(context).medicines)


GET_CONFIRMED_MEDICINES = Tool(
    name="get_confirmed_medicines",
    description=(
        "List every medicine the patient confirmed from their discharge papers: name, other "
        "names, dose, how often, timing, status (NEW, CHANGED, STOPPED, CONTINUED, AS_NEEDED), "
        "end date, the exact quote from the papers and its page. Doses and names come only "
        "from here."
    ),
    input_model=NoInput,
    handler=_get_confirmed_medicines,
)


# --- get_schedule ---


class ScheduleAnswer(BaseModel):
    """The schedule without the planning-form extras, so the model gets a shorter result."""

    daily: list[DoseTime]
    needs_timing: list[MedicineLine]
    as_needed: list[MedicineLine]
    stopped: list[MedicineLine]
    follow_ups: list[FollowUpLine]


def _get_schedule(context: ToolContext, _arguments: NoInput) -> ScheduleAnswer:
    profile = confirmed_profile(context)
    schedule = build_schedule(profile, load_plan(context.db, context.patient_id, profile))
    # `chosen` marks a time the patient picked themselves, as opposed to the papers' words.
    return ScheduleAnswer(**schedule.model_dump(include=set(ScheduleAnswer.model_fields)))


GET_SCHEDULE = Tool(
    name="get_schedule",
    description=(
        "The medicine schedule and follow-up visits, built by code from the confirmed papers and "
        "the patient's own reminder choices. Times with chosen=true were picked by the patient; "
        "how_often is always the papers' own words. Use this for questions about when."
    ),
    input_model=NoInput,
    handler=_get_schedule,
)


# --- search_patient_document ---


class Passage(BaseModel):
    id: str  # such as "D1"; the answer cites this ID
    page: int
    section: str
    text: str


class DocumentSearch(Protocol):
    """What the retriever must offer. It must filter by patient_id itself, in code."""

    def search(self, patient_id: str, query: str, limit: int) -> list[Passage]: ...


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1, max_length=300, description="What to look for, using the medicine's name"
    )


class Passages(BaseModel):
    passages: list[Passage]


def _search_patient_document(context: ToolContext, arguments: SearchInput) -> Passages:
    if context.search is None:
        raise ToolError("Searching the papers is not available.")
    # The patient comes from the context, so the model cannot ask for anyone else's papers.
    found = context.search.search(context.patient_id, arguments.query, MAX_PASSAGES)
    return Passages(passages=found[:MAX_PASSAGES])


SEARCH_PATIENT_DOCUMENT = Tool(
    name="search_patient_document",
    description=(
        "Search the patient's own confirmed discharge papers and return up to 4 passages with an "
        "ID (such as D1), the page and the section. Cite the ID. If nothing relevant comes back, "
        "the answer is that it is not in their papers."
    ),
    input_model=SearchInput,
    handler=_search_patient_document,
)
