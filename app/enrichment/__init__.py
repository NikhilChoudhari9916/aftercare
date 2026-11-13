from functools import lru_cache

import httpx

from app.config import get_settings
from app.enrichment.cache import TtlCache
from app.enrichment.openfda import OpenFdaClient
from app.enrichment.rxnorm import RxNormClient

__all__ = ["OpenFdaClient", "RxNormClient", "get_openfda", "get_rxnorm"]


@lru_cache
def _http() -> httpx.Client:
    return httpx.Client(timeout=get_settings().external_timeout_seconds)


@lru_cache
def get_rxnorm() -> RxNormClient:
    settings = get_settings()
    cache = TtlCache(settings.external_cache_days * 86400)
    return RxNormClient(_http(), settings.rxnav_base_url, cache)


@lru_cache
def get_openfda() -> OpenFdaClient:
    settings = get_settings()
    cache = TtlCache(settings.external_cache_days * 86400)
    return OpenFdaClient(_http(), settings.openfda_base_url, cache, settings.label_section_chars)
