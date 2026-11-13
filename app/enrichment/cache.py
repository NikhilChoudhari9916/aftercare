import time
from collections.abc import Callable
from typing import Any


class ExternalError(Exception):
    """A public lookup service did not answer. The message is plain and safe to show."""


class TtlCache:
    """Remembers answers from outside services for a while, so we ask each question once a week."""

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._items: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if self._clock() - stored_at > self._ttl:
            del self._items[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._items[key] = (self._clock(), value)
