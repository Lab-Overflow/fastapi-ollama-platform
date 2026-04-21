import hashlib
import json
import re
import time
from collections import deque
from pathlib import Path
from threading import Lock


class SessionStore:
    """Conversation memory with in-memory cache + JSONL persistence."""

    def __init__(
        self,
        max_turns: int = 20,
        ttl_seconds: int = 3600,
        storage_dir: str = "data/sessions",
    ) -> None:
        self._data: dict[str, tuple[float, deque[dict[str, str]]]] = {}
        self._max_turns = max_turns
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def get(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            self._evict()
            entry = self._data.get(session_id)
            if entry:
                return list(entry[1])

            restored = self._load_from_disk(session_id)
            if restored:
                buf = deque(restored, maxlen=self._max_turns * 2)
                self._data[session_id] = (time.time(), buf)
                return list(buf)
            return []

    def append(self, session_id: str, messages: list[dict[str, str]]) -> None:
        with self._lock:
            _, buf = self._data.setdefault(
                session_id, (time.time(), deque(maxlen=self._max_turns * 2))
            )
            ts = time.time()
            valid_messages: list[dict[str, str]] = []
            for m in messages:
                role = str(m.get("role", "")).strip()
                content = m.get("content", "")
                if role not in {"system", "user", "assistant"}:
                    continue
                if not isinstance(content, str):
                    content = str(content)
                normalized = {"role": role, "content": content}
                valid_messages.append(normalized)
                buf.append(normalized)

            if valid_messages:
                self._append_to_disk(session_id, valid_messages, ts)
            self._data[session_id] = (ts, buf)

    def _evict(self) -> None:
        now = time.time()
        stale = [k for k, (ts, _) in self._data.items() if now - ts > self._ttl]
        for k in stale:
            self._data.pop(k, None)

    def _session_path(self, session_id: str) -> Path:
        compact = re.sub(r"[^a-zA-Z0-9._-]+", "_", session_id).strip("._-")
        if not compact:
            compact = "session"
        compact = compact[:48]
        digest = hashlib.sha1(session_id.encode("utf-8")).hexdigest()[:12]
        return self._storage_dir / f"{compact}-{digest}.jsonl"

    def _append_to_disk(self, session_id: str, messages: list[dict[str, str]], ts: float) -> None:
        path = self._session_path(session_id)
        with path.open("a", encoding="utf-8") as f:
            for m in messages:
                record = {
                    "ts": ts,
                    "session_id": session_id,
                    "role": m["role"],
                    "content": m["content"],
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _load_from_disk(self, session_id: str) -> list[dict[str, str]]:
        path = self._session_path(session_id)
        if not path.exists():
            return []

        restored = deque(maxlen=self._max_turns * 2)
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if record.get("session_id") != session_id:
                    continue
                role = record.get("role")
                content = record.get("content")
                if role not in {"system", "user", "assistant"}:
                    continue
                if not isinstance(content, str):
                    content = str(content)
                restored.append({"role": role, "content": content})
        return list(restored)
