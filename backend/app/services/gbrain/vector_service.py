"""
Vector memory (Stage 7).

`LocalVectorStore` is an in-process, dependency-free semantic index: it embeds
each chunk with a deterministic hashing bag-of-words vectoriser and ranks by
cosine similarity. It satisfies `AbstractVectorStore`, so swapping in Qdrant,
Chroma or PGVector is a one-line change in `build_vector_store`.

The embedding is intentionally simple and offline. Replace `embed` with a real
sentence-transformer / API embedder for production-grade recall.
"""
from __future__ import annotations

import hashlib
import math
import re

import numpy as np

from app.core.config import Settings
from app.utils.logger import get_logger

logger = get_logger("vector")

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _stable_hash(token: str) -> int:
    """Process-independent hash (unlike builtin hash(), which is salted)."""
    return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def embed(text: str, dim: int) -> np.ndarray:
    """Deterministic hashing embedding, L2-normalised."""
    vec = np.zeros(dim, dtype=np.float32)
    for tok in _tokens(text):
        h = _stable_hash(tok) % dim
        sign = 1.0 if (_stable_hash(tok + "#") & 1) else -1.0
        vec[h] += sign
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


class LocalVectorStore:
    """In-memory cosine index. Lives for the process lifetime."""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._vectors: list[np.ndarray] = []
        self._payloads: list[dict] = []

    def upsert(self, meeting_id: str, chunks: list[dict]) -> None:
        for c in chunks:
            self._vectors.append(embed(c["content"], self.dim))
            self._payloads.append(
                {
                    "content": c["content"],
                    "speaker": c.get("speaker"),
                    "meeting_id": meeting_id,
                }
            )
        logger.info("Indexed %d chunks for meeting %s", len(chunks), meeting_id)

    def search(
        self,
        query: str,
        meeting_id: str | None,
        top_k: int,
        meeting_ids: list[str] | None = None,
    ) -> list[dict]:
        if not self._vectors:
            return []
        scope = set(meeting_ids) if meeting_ids is not None else None
        q = embed(query, self.dim)
        matrix = np.vstack(self._vectors)
        scores = matrix @ q  # cosine, vectors are normalised
        order = np.argsort(scores)[::-1]
        results: list[dict] = []
        for idx in order:
            payload = self._payloads[idx]
            if meeting_id and payload["meeting_id"] != meeting_id:
                continue
            if scope is not None and payload["meeting_id"] not in scope:
                continue
            score = float(scores[idx])
            if math.isnan(score) or score <= 0:
                continue
            results.append({**payload, "score": round(score, 4)})
            if len(results) >= top_k:
                break
        return results

    def delete(self, meeting_id: str) -> None:
        """Drop every vector belonging to a meeting (used on meeting delete)."""
        kept_vecs: list[np.ndarray] = []
        kept_pay: list[dict] = []
        for vec, pay in zip(self._vectors, self._payloads):
            if pay["meeting_id"] != meeting_id:
                kept_vecs.append(vec)
                kept_pay.append(pay)
        removed = len(self._vectors) - len(kept_vecs)
        self._vectors, self._payloads = kept_vecs, kept_pay
        if removed:
            logger.info("Removed %d vectors for meeting %s", removed, meeting_id)


def build_vector_store(settings: Settings):
    """Factory selecting the configured vector backend."""
    backend = settings.vector_backend
    if backend == "local":
        return LocalVectorStore(dim=settings.vector_dim)
    if backend == "qdrant":
        # from app.services.gbrain.qdrant_store import QdrantVectorStore
        # return QdrantVectorStore(settings)
        raise NotImplementedError(
            "Qdrant backend selected but driver not wired. "
            "Install qdrant-client and provide a QdrantVectorStore "
            "implementing AbstractVectorStore."
        )
    if backend in {"chroma", "pgvector"}:
        raise NotImplementedError(
            f"'{backend}' backend selected but not wired. Implement "
            "AbstractVectorStore for it and register here."
        )
    raise ValueError(f"Unknown vector backend: {backend}")
