"""Dashboard endpoint: high-level memory stats for the UI."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.graph_repository import GraphRepository
from app.repositories.meeting_repository import MeetingRepository

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardStats(BaseModel):
    meetings: int
    chunks: int
    graph_edges: int
    open_action_items: int
    hermes_provider: str
    vector_backend: str


@router.get("/stats", response_model=DashboardStats)
def stats(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return DashboardStats(
        meetings=MeetingRepository(db).count(),
        chunks=ChunkRepository(db).count_chunks(),
        graph_edges=GraphRepository(db).count(),
        open_action_items=ChunkRepository(db).count_open_action_items(),
        hermes_provider=settings.hermes_provider,
        vector_backend=settings.vector_backend,
    )
