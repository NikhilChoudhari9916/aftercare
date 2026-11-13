import httpx
from pydantic import BaseModel

from app.enrichment.cache import ExternalError, TtlCache

DAILYMED_URL = "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid="
CANDIDATES = 5


def _single_ingredient(labels: list[dict], name: str) -> dict:
    """Prefer the label for this medicine alone over a combination product.

    A search for "lisinopril" can return "lisinopril and hydrochlorothiazide" first, whose
    purpose and warnings describe a different medicine.
    """
    for label in labels:
        generic = [g.casefold() for g in label.get("openfda", {}).get("generic_name", [])]
        brand = [b.casefold() for b in label.get("openfda", {}).get("brand_name", [])]
        if generic == [name.casefold()] or name.casefold() in brand:
            return label
    return labels[0]


class LabelText(BaseModel):
    """What the official label says a medicine is for and warns about. Never how much to take."""

    found: bool
    medicine: str
    purpose: str | None = None
    warnings: str | None = None
    boxed_warning: str | None = None
    source_url: str | None = None
    label_date: str | None = None  # YYYYMMDD, as openFDA writes it


class OpenFdaClient:
    """Reads only the "indications and usage" and "warnings" parts of an FDA drug label.

    The dosage part is never read, so a general dose from a label cannot reach an answer.
    The patient's own doses come from their confirmed papers only (ADR-0027).
    """

    def __init__(
        self, http: httpx.Client, base_url: str, cache: TtlCache, max_chars: int = 1500
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._cache = cache
        self._max_chars = max_chars

    def get_label(self, names: list[str]) -> LabelText:
        """Try each name (generic first, then brand) until a label is found."""
        names = [" ".join(name.replace('"', " ").split()) for name in names if name.strip()]
        if not names:
            return LabelText(found=False, medicine="")
        key = "openfda:" + "|".join(name.casefold() for name in names)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = LabelText(found=False, medicine=names[0])
        for name in names:
            label = self._find(name)
            if label is not None:
                result = self._read(name, label)
                break
        self._cache.set(key, result)
        return result

    def _find(self, name: str) -> dict | None:
        for field in ("generic_name", "brand_name"):
            params = {"search": f'openfda.{field}:"{name}"', "limit": str(CANDIDATES)}
            try:
                response = self._http.get(f"{self._base_url}/drug/label.json", params=params)
                if response.status_code == 404:  # openFDA's way of saying "no match"
                    continue
                response.raise_for_status()
                results = response.json().get("results") or []
            except (httpx.HTTPError, ValueError) as error:
                raise ExternalError("The drug label service is not reachable right now.") from error
            if results:
                return _single_ingredient(results, name)
        return None

    def _read(self, name: str, label: dict) -> LabelText:
        set_id = label.get("set_id")
        return LabelText(
            found=True,
            medicine=name,
            purpose=self._section(label, "indications_and_usage"),
            warnings=self._section(label, "warnings", "warnings_and_cautions"),
            boxed_warning=self._section(label, "boxed_warning"),
            source_url=DAILYMED_URL + set_id if set_id else None,
            label_date=label.get("effective_time"),
        )

    def _section(self, label: dict, *keys: str) -> str | None:
        for key in keys:
            parts = label.get(key)
            if parts:
                text = " ".join(" ".join(parts).split())
                if len(text) > self._max_chars:
                    text = text[: self._max_chars].rsplit(" ", 1)[0] + " ..."
                return text
        return None
