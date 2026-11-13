from pydantic import BaseModel, ConfigDict, Field

from app.enrichment.cache import ExternalError
from app.enrichment.openfda import LabelText
from app.enrichment.rxnorm import RxNormResult
from app.tools.profile_tools import confirmed_profile
from app.tools.registry import Tool, ToolContext, ToolError


class MedicineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medicine: str = Field(
        min_length=1,
        max_length=80,
        description="A medicine's name, brand or generic, as the patient's papers write it",
    )


# --- search_fda_label ---


def _search_fda_label(context: ToolContext, arguments: MedicineInput) -> LabelText:
    if context.openfda is None:
        raise ToolError("The drug label service is not available.")
    asked = arguments.medicine.strip().casefold()
    for medicine in confirmed_profile(context).medicines:
        names = [medicine.name_as_written, *medicine.other_names]
        if asked in (name.casefold() for name in names):
            try:
                return context.openfda.get_label(names)
            except ExternalError as error:
                raise ToolError(str(error)) from error
    # Only the patient's confirmed medicines get a label lookup (CLAUDE.md section 2).
    raise ToolError("That is not one of the patient's confirmed medicines.")


SEARCH_FDA_LABEL = Tool(
    name="search_fda_label",
    description=(
        "What the official FDA drug label says a confirmed medicine is for and its warnings "
        "(including any boxed warning). It never returns dosage: doses come only from the "
        "patient's papers. Say 'The label says...'. Use it only to explain, never to add to or "
        "override the papers."
    ),
    input_model=MedicineInput,
    handler=_search_fda_label,
)


# --- lookup_rxnorm ---


class NameInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80, description="A brand or generic medicine name")


def _lookup_rxnorm(context: ToolContext, arguments: NameInput) -> RxNormResult:
    if context.rxnorm is None:
        raise ToolError("The medicine name service is not available.")
    try:
        return context.rxnorm.lookup(arguments.name)
    except ExternalError as error:
        raise ToolError(str(error)) from error


LOOKUP_RXNORM = Tool(
    name="lookup_rxnorm",
    description=(
        "Find the generic name and the brand names for a medicine name (for example Lasix and "
        "furosemide). Use it to match a name in a question with a name in the papers. It never "
        "suggests a product to buy."
    ),
    input_model=NameInput,
    handler=_lookup_rxnorm,
)
