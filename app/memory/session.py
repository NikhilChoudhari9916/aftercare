"""Short-term memory for one conversation (ADR-0029, ADR-0036).

It keeps the last few questions and answers and the medicine in focus, so that "it" and "that
pill" can be understood in the next turn. It lives only in this process's memory: nothing is
written to disk or to a log, and it is dropped after a long idle time or when the server
restarts. It is keyed by the login session and the patient, so another person or another
patient never sees it. It holds patient text, so never log what is inside it (ADR-0031).
"""

import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from app.config import get_settings

IDLE_SECONDS = 12 * 3600  # the same limit as an idle login session
MAX_CONVERSATIONS = 500  # a hard cap so the server cannot grow without bound


@dataclass(frozen=True)
class Turn:
    question: str
    answer: str


@dataclass(frozen=True)
class Recall:
    """A copy of what was remembered, safe to read without a lock."""

    turns: tuple[Turn, ...] = ()
    focus_medicine: str | None = None


@dataclass
class _Entry:
    turns: deque[Turn]
    focus_medicine: str | None
    last_used: float


class SessionMemory:
    def __init__(
        self,
        max_turns: int,
        *,
        idle_seconds: float = IDLE_SECONDS,
        max_conversations: int = MAX_CONVERSATIONS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_turns = max_turns
        self._idle_seconds = idle_seconds
        self._max_conversations = max_conversations
        self._clock = clock
        self._items: OrderedDict[tuple[str, str], _Entry] = OrderedDict()
        self._lock = threading.Lock()

    def recall(self, session_key: str, patient_id: str) -> Recall:
        with self._lock:
            self._drop_idle()
            entry = self._items.get((session_key, patient_id))
            if entry is None:
                return Recall()
            return Recall(turns=tuple(entry.turns), focus_medicine=entry.focus_medicine)

    def remember(
        self,
        session_key: str,
        patient_id: str,
        question: str,
        answer: str,
        focus_medicine: str | None,
    ) -> None:
        """Add one turn. A question that names no medicine keeps the one already in focus."""
        key = (session_key, patient_id)
        with self._lock:
            self._drop_idle()
            entry = self._items.get(key)
            if entry is None:
                entry = _Entry(deque(maxlen=self._max_turns), None, self._clock())
                self._items[key] = entry
            entry.turns.append(Turn(question=question, answer=answer))
            if focus_medicine:
                entry.focus_medicine = focus_medicine
            entry.last_used = self._clock()
            self._items.move_to_end(key)
            while len(self._items) > self._max_conversations:
                self._items.popitem(last=False)

    def forget(self, session_key: str) -> None:
        """Drop everything for one login session (for example when it ends)."""
        with self._lock:
            for key in [key for key in self._items if key[0] == session_key]:
                del self._items[key]

    def _drop_idle(self) -> None:
        now = self._clock()
        for key in [k for k, e in self._items.items() if now - e.last_used > self._idle_seconds]:
            del self._items[key]


@lru_cache
def get_session_memory() -> SessionMemory:
    return SessionMemory(get_settings().session_memory_turns)
