from datetime import date

from app.extraction.schema import MedStatus
from app.summary.profile import ConfirmedProfile
from tests.samples import medicine, patient1_profile


def confirmed(**changes) -> ConfirmedProfile:
    """Patient 1 as a confirmed profile; pass fields to replace."""
    extracted = patient1_profile()
    fields = {
        "version_id": "version-1",
        "version": 1,
        "confirmed_at": None,
        "discharge_date": date(2026, 10, 12),
        **extracted.model_dump(exclude={"discharge_date"}),
    }
    fields.update(changes)
    return ConfirmedProfile(**fields)


def with_medicine(frequency, *, status=MedStatus.CONTINUED, as_needed=False, **fields):
    """A single-medicine profile, for checking how one frequency is read."""
    item = medicine("testol", [], "10 mg", frequency, status, "quote", as_needed=as_needed)
    item = item.model_copy(update=fields)
    return confirmed(medicines=[item], follow_ups=[])
