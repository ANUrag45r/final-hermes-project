"""
Abstract interfaces for the GBrain memory layer.

These Protocols are the seams that keep the system SOLID: the ingestion and
chat services depend on `AbstractGBrain`, not on any concrete implementation.
Swapping the bundled local memory for the *real* installed GBrain means
providing another class that satisfies `AbstractGBrain` — no business logic
changes.

Hard rule from the spec: GBrain stores and retrieves. It NEVER generates answers.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.chat_schema import RAGContext


@runtime_checkable
class AbstractChunker(Protocol):
    def chunk(self, transcript: str) -> list[dict]: ...


@runtime_checkable
class AbstractEntityExtractor(Protocol):
    def extract(self, chunks: list[dict]) -> list[dict]: ...


@runtime_checkable
class AbstractGraphExtractor(Protocol):
    def extract(self, chunks: list[dict], entities: list[dict]) -> list[dict]: ...


@runtime_checkable
class AbstractVectorStore(Protocol):
    def upsert(self, meeting_id: str, chunks: list[dict]) -> None: ...
    def search(
        self,
        query: str,
        meeting_id: str | None,
        top_k: int,
        meeting_ids: list[str] | None = None,
    ) -> list[dict]: ...
    def delete(self, meeting_id: str) -> None: ...


@runtime_checkable
class AbstractGBrain(Protocol):
    """The sole memory engine: ingest knowledge, search for evidence."""

    def ingest(self, meeting_id: str, transcript: str) -> dict: ...

    def search(
        self,
        query: str,
        meeting_id: str | None = None,
        top_k: int = 4,
        meeting_ids: list[str] | None = None,
    ) -> RAGContext: ...

    def delete(self, meeting_id: str) -> None: ...
