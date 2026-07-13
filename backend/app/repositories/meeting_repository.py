"""Meeting repository — the only place that reads/writes Meeting rows."""
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.action_item import ActionItem
from app.models.entity import Entity
from app.models.graph_edge import GraphEdge
from app.models.meeting import Meeting
from app.models.transcript_chunk import TranscriptChunk


class MeetingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        meeting_id: str,
        title: str,
        transcript: str,
        duration: int | None,
        project_id: int | None = None,
    ) -> Meeting:
        meeting = Meeting(
            meeting_id=meeting_id,
            title=title,
            raw_transcript=transcript,
            duration=duration,
            project_id=project_id,
        )
        self.db.add(meeting)
        self.db.flush()
        return meeting

    def meeting_ids_for_project(self, project_id: int) -> list[str]:
        return list(
            self.db.scalars(
                select(Meeting.meeting_id).where(Meeting.project_id == project_id)
            ).all()
        )

    def list_projects(self) -> list[dict]:
        """Distinct projects with their meeting counts and titles."""
        rows = self.db.execute(
            select(Meeting.project_id, func.count(Meeting.id))
            .where(Meeting.project_id.is_not(None))
            .group_by(Meeting.project_id)
            .order_by(Meeting.project_id)
        ).all()
        out = []
        for pid, count in rows:
            titles = list(
                self.db.scalars(
                    select(Meeting.title).where(Meeting.project_id == pid).limit(5)
                ).all()
            )
            out.append({"project_id": pid, "meetings": count, "titles": titles})
        return out

    def get(self, meeting_id: str) -> Meeting | None:
        return self.db.scalar(
            select(Meeting).where(Meeting.meeting_id == meeting_id)
        )

    def get_with_relations(self, meeting_id: str) -> Meeting | None:
        return self.db.scalar(
            select(Meeting)
            .where(Meeting.meeting_id == meeting_id)
            .options(
                selectinload(Meeting.chunks),
                selectinload(Meeting.entities),
                selectinload(Meeting.edges),
                selectinload(Meeting.action_items),
            )
        )

    def list_all(self) -> list[Meeting]:
        return list(
            self.db.scalars(select(Meeting).order_by(Meeting.date.desc())).all()
        )

    def count(self) -> int:
        return int(self.db.scalar(select(func.count(Meeting.id))) or 0)

    def update_fields(
        self,
        meeting: Meeting,
        title: str | None = None,
        transcript: str | None = None,
        duration: int | None = None,
    ) -> Meeting:
        if title is not None:
            meeting.title = title
        if transcript is not None:
            meeting.raw_transcript = transcript
        if duration is not None:
            meeting.duration = duration
        self.db.flush()
        return meeting

    def clear_derived(self, meeting_id: str) -> None:
        """Delete chunks/entities/edges/action items but keep the meeting row.

        Used when a meeting is edited and its memory must be rebuilt.
        """
        for table in (TranscriptChunk, Entity, GraphEdge, ActionItem):
            self.db.execute(delete(table).where(table.meeting_id == meeting_id))
        self.db.flush()

    def delete(self, meeting: Meeting) -> None:
        """Delete a meeting and (via ORM cascade) all its derived rows."""
        self.db.delete(meeting)
        self.db.flush()
