"""GraphEdge: a knowledge-graph relationship (Stage 6).

Stored as (source) --[relation]--> (target), e.g. Bob responsible_for Authentication.
"""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class GraphEdge(Base):
    __tablename__ = "knowledge_graph_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("meetings.meeting_id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(255), index=True)
    relation: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(255), index=True)

    meeting: Mapped["Meeting"] = relationship(back_populates="edges")  # noqa: F821
