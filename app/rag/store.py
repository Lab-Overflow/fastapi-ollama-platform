import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

import numpy as np


@dataclass
class Chunk:
    id: str
    text: str
    embedding: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)


class InMemoryVectorStore:
    """Minimal cosine-similarity store. Replace with Qdrant/Milvus in prod."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._lock = Lock()

    def add(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str | None] | None = None,
    ) -> list[str]:
        metadatas = metadatas or [{} for _ in texts]
        ids = ids or [None] * len(texts)
        added: list[str] = []
        with self._lock:
            for text, emb, meta, cid in zip(texts, embeddings, metadatas, ids, strict=True):
                chunk_id = cid or uuid.uuid4().hex
                vec = np.asarray(emb, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                self._chunks.append(Chunk(chunk_id, text, vec, meta))
                added.append(chunk_id)
        return added

    def search(self, query_embedding: list[float], top_k: int = 4) -> list[tuple[Chunk, float]]:
        with self._lock:
            if not self._chunks:
                return []
            q = np.asarray(query_embedding, dtype=np.float32)
            q_norm = np.linalg.norm(q)
            if q_norm == 0:
                return []
            q = q / q_norm
            matrix = np.stack([c.embedding for c in self._chunks])
            scores = matrix @ q
            idx = np.argsort(-scores)[:top_k]
            return [(self._chunks[i], float(scores[i])) for i in idx]

    @property
    def size(self) -> int:
        return len(self._chunks)
