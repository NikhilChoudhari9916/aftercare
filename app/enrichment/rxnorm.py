import httpx
from pydantic import BaseModel

from app.enrichment.cache import ExternalError, TtlCache

MAX_OTHER_NAMES = 8


class RxNormResult(BaseModel):
    found: bool
    rxcui: str | None = None
    ingredient: str | None = None  # the generic name, such as furosemide
    other_names: list[str] = []  # brand names and the generic, without the name that was asked


class RxNormClient:
    """Turns a medicine name ("Lasix") into its official ID and other names (furosemide)."""

    def __init__(self, http: httpx.Client, base_url: str, cache: TtlCache) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._cache = cache

    def lookup(self, name: str) -> RxNormResult:
        name = " ".join(name.split())
        key = f"rxnorm:{name.casefold()}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._lookup(name)
        self._cache.set(key, result)
        return result

    def _lookup(self, name: str) -> RxNormResult:
        ids = self._get("/rxcui.json", {"name": name}).get("idGroup", {}).get("rxnormId") or []
        if not ids:
            return RxNormResult(found=False)
        rxcui = ids[0]
        related = self._related(rxcui)
        ingredients = related.get("IN", [])
        brands = related.get("BN", [])
        if ingredients and ingredients[0][0] != rxcui:
            # The name was a brand, which only lists itself. Ask the generic for all its brands.
            brands = self._related(ingredients[0][0]).get("BN", [])

        names: list[str] = []
        for _, other in [*ingredients, *brands]:
            if "substance" in other.casefold():  # RxNorm also lists bare ingredients this way
                continue
            if other.casefold() != name.casefold() and other not in names:
                names.append(other)
        return RxNormResult(
            found=True,
            rxcui=rxcui,
            ingredient=ingredients[0][1] if ingredients else None,
            other_names=names[:MAX_OTHER_NAMES],
        )

    def _related(self, rxcui: str) -> dict[str, list[tuple[str, str]]]:
        """Brand (BN) and ingredient (IN) names tied to one RxNorm ID, as (id, name) pairs."""
        # A space is sent as "+", which is how RxNorm wants two term types listed.
        data = self._get(f"/rxcui/{rxcui}/related.json", {"tty": "BN IN"})
        groups = data.get("relatedGroup", {}).get("conceptGroup") or []
        return {
            group["tty"]: [(c["rxcui"], c["name"]) for c in group.get("conceptProperties") or []]
            for group in groups
        }

    def _get(self, path: str, params: dict[str, str]) -> dict:
        try:
            response = self._http.get(self._base_url + path, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ExternalError("The medicine name service is not reachable right now.") from error
