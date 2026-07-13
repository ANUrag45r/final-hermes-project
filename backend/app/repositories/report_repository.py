"""
Read-only aggregation queries for reports.

Keeps report-specific querying out of the per-entity repositories while still
being the only place that touches the DB for this feature.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.action_item import ActionItem
from app.models.entity import Entity
from app.models.graph_edge import GraphEdge
from app.models.meeting import Meeting
from app.models.transcript_chunk import TranscriptChunk


class ReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def meeting(self, meeting_id: str) -> Meeting | None:
        return self.db.scalar(
            select(Meeting).where(Meeting.meeting_id == meeting_id)
        )

    def meetings_in_range(self, start: datetime, end: datetime) -> list[Meeting]:
        return list(
            self.db.scalars(
                select(Meeting)
                .where(Meeting.date >= start, Meeting.date <= end)
                .order_by(Meeting.date.asc())
            ).all()
        )

    def meetings_for_project(self, project_id: int) -> list[Meeting]:
        return list(
            self.db.scalars(
                select(Meeting)
                .where(Meeting.project_id == project_id)
                .order_by(Meeting.date.asc())
            ).all()
        )

    def all_meetings(self) -> list[Meeting]:
        return list(
            self.db.scalars(select(Meeting).order_by(Meeting.date.asc())).all()
        )

    # --- bulk fetches scoped to a set of meeting ids ---
    def chunks_for(self, meeting_ids: list[str]) -> list[TranscriptChunk]:
        if not meeting_ids:
            return []
        return list(
            self.db.scalars(
                select(TranscriptChunk).where(
                    TranscriptChunk.meeting_id.in_(meeting_ids)
                )
            ).all()
        )

    def entities_for(self, meeting_ids: list[str]) -> list[Entity]:
        if not meeting_ids:
            return []
        return list(
            self.db.scalars(
                select(Entity).where(Entity.meeting_id.in_(meeting_ids))
            ).all()
        )

    def edges_for(self, meeting_ids: list[str]) -> list[GraphEdge]:
        if not meeting_ids:
            return []
        return list(
            self.db.scalars(
                select(GraphEdge).where(GraphEdge.meeting_id.in_(meeting_ids))
            ).all()
        )

    def action_items_for(self, meeting_ids: list[str]) -> list[ActionItem]:
        if not meeting_ids:
            return []
        return list(
            self.db.scalars(
                select(ActionItem).where(ActionItem.meeting_id.in_(meeting_ids))
            ).all()
        )
