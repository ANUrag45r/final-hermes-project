"""ActionItem: a derived, trackable task surfaced to the UI."""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("meetings.meeting_id", ondelete="CASCADE"), index=True
    )
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    task: Mapped[str] = mapped_column(String(512))
    due: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open")  # open | done

    meeting: Mapped["Meeting"] = relationship(  # noqa: F821
        back_populates="action_items"
    )
