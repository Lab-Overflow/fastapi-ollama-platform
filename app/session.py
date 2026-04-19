import time
from collections import deque
from threading import Lock


class SessionStore:
    """In-memory conversation memory. Swap with Redis for production."""

    def __init__(self, max_turns: int = 20, ttl_seconds: int = 3600) -> None:
        self._data: dict[str, tuple[float, deque[dict[str, str]]]] = {}
        self._max_turns = max_turns
        self._ttl = ttl_seconds
        self._lock = Lock()

    def get(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            self._evict()
            entry = self._data.get(session_id)
            return list(entry[1]) if entry else []

    def append(self, session_id: str, messages: list[dict[str, str]]) -> None:
        with self._lock:
            _, buf = self._data.setdefault(
                session_id, (time.time(), deque(maxlen=self._max_turns * 2))
            )
            for m in messages:
                buf.append(m)
            self._data[session_id] = (time.time(), buf)

    def _evict(self) -> None:
        now = time.time()
        stale = [k for k, (ts, _) in self._data.items() if now - ts > self._ttl]
        for k in stale:
            self._data.pop(k, None)
