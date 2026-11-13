from app.tools.label_tools import LOOKUP_RXNORM, SEARCH_FDA_LABEL
from app.tools.profile_tools import GET_CONFIRMED_MEDICINES, GET_SCHEDULE, SEARCH_PATIENT_DOCUMENT
from app.tools.registry import ToolContext, ToolError, ToolRegistry

__all__ = ["ToolContext", "ToolError", "ToolRegistry", "default_registry"]


def default_registry() -> ToolRegistry:
    """Every tool there is. Each agent is given only the ones it needs, with `only`."""
    return ToolRegistry(
        [
            GET_CONFIRMED_MEDICINES,
            GET_SCHEDULE,
            SEARCH_PATIENT_DOCUMENT,
            SEARCH_FDA_LABEL,
            LOOKUP_RXNORM,
        ]
    )
