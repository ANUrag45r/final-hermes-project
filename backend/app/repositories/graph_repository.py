"""Repository for the knowledge-graph edges."""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.graph_edge import GraphEdge


class GraphRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def bulk_add_edges(self, meeting_id: str, edges: list[dict]) -> None:
        self.db.add_all(
            GraphEdge(
                meeting_id=meeting_id,
                source=e["source"],
                relation=e["relation"],
                target=e["target"],
            )
            for e in edges
        )
        self.db.flush()

    def search(
        self,
        term: str,
        meeting_id: str | None = None,
        meeting_ids: list[str] | None = None,
        limit: int = 25,
    ) -> list[GraphEdge]:
        """Match edges whose source or target contains the term (case-insensitive)."""
        like = f"%{term.lower()}%"
        stmt = select(GraphEdge).where(
            or_(
                func.lower(GraphEdge.source).like(like),
                func.lower(GraphEdge.target).like(like),
            )
        )
        if meeting_id:
            stmt = stmt.where(GraphEdge.meeting_id == meeting_id)
        elif meeting_ids is not None:
            stmt = stmt.where(GraphEdge.meeting_id.in_(meeting_ids))
        return list(self.db.scalars(stmt.limit(limit)).all())

    def count(self) -> int:
        return int(self.db.scalar(select(func.count(GraphEdge.id))) or 0)
