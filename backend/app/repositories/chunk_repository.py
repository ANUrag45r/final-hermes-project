"""Repository for transcript chunks, entities and action items."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.action_item import ActionItem
from app.models.entity import Entity
from app.models.transcript_chunk import TranscriptChunk


class ChunkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- chunks ---
    def bulk_add_chunks(
        self, meeting_id: str, chunks: list[dict]
    ) -> list[TranscriptChunk]:
        rows = [
            TranscriptChunk(
                meeting_id=meeting_id,
                chunk_index=c["chunk_index"],
                speaker=c.get("speaker"),
                content=c["content"],
            )
            for c in chunks
        ]
        self.db.add_all(rows)
        self.db.flush()
        return rows

    def all_chunks(self, meeting_id: str | None = None) -> list[TranscriptChunk]:
        stmt = select(TranscriptChunk)
        if meeting_id:
            stmt = stmt.where(TranscriptChunk.meeting_id == meeting_id)
        return list(self.db.scalars(stmt).all())

    def count_chunks(self) -> int:
        return int(self.db.scalar(select(func.count(TranscriptChunk.id))) or 0)

    # --- entities ---
    def bulk_add_entities(self, meeting_id: str, entities: list[dict]) -> None:
        self.db.add_all(
            Entity(meeting_id=meeting_id, name=e["name"], type=e["type"])
            for e in entities
        )
        self.db.flush()

    # --- action items ---
    def bulk_add_action_items(self, meeting_id: str, items: list[dict]) -> None:
        self.db.add_all(
            ActionItem(
                meeting_id=meeting_id,
                owner=i.get("owner"),
                task=i["task"],
                due=i.get("due"),
                status=i.get("status", "open"),
            )
            for i in items
        )
        self.db.flush()

    def list_action_items(self, meeting_id: str | None = None) -> list[ActionItem]:
        stmt = select(ActionItem)
        if meeting_id:
            stmt = stmt.where(ActionItem.meeting_id == meeting_id)
        return list(self.db.scalars(stmt).all())

    def count_open_action_items(self) -> int:
        return int(
            self.db.scalar(
                select(func.count(ActionItem.id)).where(ActionItem.status == "open")
            )
            or 0
        )
