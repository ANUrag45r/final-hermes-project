"""Meeting: raw persistence layer (Stage 2). No intelligence lives here."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="Untitled Meeting")
    raw_transcript: Mapped[str] = mapped_column(Text)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # minutes
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    chunks: Mapped[list["TranscriptChunk"]] = relationship(  # noqa: F821
        back_populates="meeting", cascade="all, delete-orphan"
    )
    entities: Mapped[list["Entity"]] = relationship(  # noqa: F821
        back_populates="meeting", cascade="all, delete-orphan"
    )
    edges: Mapped[list["GraphEdge"]] = relationship(  # noqa: F821
        back_populates="meeting", cascade="all, delete-orphan"
    )
    action_items: Mapped[list["ActionItem"]] = relationship(  # noqa: F821
        back_populates="meeting", cascade="all, delete-orphan"
    )
