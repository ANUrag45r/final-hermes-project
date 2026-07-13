"""TranscriptChunk: a single speaker turn (Stage 4)."""
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("meetings.meeting_id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content: Mapped[str] = mapped_column(Text)

    meeting: Mapped["Meeting"] = relationship(back_populates="chunks")  # noqa: F821
