"""Meeting endpoints: upload, list, detail, summary, action items."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_ingestion_service
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.meeting_schema import (
    ActionItemOut,
    IngestionResult,
    MeetingDetail,
    MeetingOut,
    MeetingUpdate,
    MeetingUpload,
    ProjectSummary,
)
from app.services.ingestion.meeting_ingestion import MeetingIngestionService

router = APIRouter(prefix="/meetings", tags=["meetings"])


from pydantic import BaseModel

class AutoIngestSettingsRequest(BaseModel):
    enabled: bool


@router.get("/auto-ingest")
def get_auto_ingest_settings(db: Session = Depends(get_db)):
    from app.models.auto_ingest_settings import AutoIngestSettings

    settings = db.query(AutoIngestSettings).first()
    if not settings:
        settings = AutoIngestSettings(enabled=False)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return {"enabled": settings.enabled}


@router.post("/auto-ingest")
def update_auto_ingest_settings(req: AutoIngestSettingsRequest, db: Session = Depends(get_db)):
    from app.models.auto_ingest_settings import AutoIngestSettings
    import datetime

    settings = db.query(AutoIngestSettings).first()
    if not settings:
        settings = AutoIngestSettings()
        db.add(settings)
    
    # Update activated_at if enabling
    if req.enabled and not settings.enabled:
        settings.activated_at = datetime.datetime.now().isoformat()
    elif not req.enabled:
        settings.activated_at = None

    settings.enabled = req.enabled
    db.commit()
    db.refresh(settings)
    return {"enabled": settings.enabled}



@router.post("/upload", response_model=IngestionResult, status_code=201)
def upload_meeting(
    payload: MeetingUpload,
    service: MeetingIngestionService = Depends(get_ingestion_service),
    db: Session = Depends(get_db),
):
    try:
        result = service.ingest(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("", response_model=list[MeetingOut])
def list_meetings(db: Session = Depends(get_db)):
    return MeetingRepository(db).list_all()


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)):
    return MeetingRepository(db).list_projects()


@router.get("/{meeting_id}", response_model=MeetingDetail)
def get_meeting(meeting_id: str, db: Session = Depends(get_db)):
    meeting = MeetingRepository(db).get_with_relations(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.get("/{meeting_id}/action-items", response_model=list[ActionItemOut])
def get_action_items(meeting_id: str, db: Session = Depends(get_db)):
    return ChunkRepository(db).list_action_items(meeting_id)


@router.patch("/{meeting_id}", response_model=IngestionResult)
def edit_meeting(
    meeting_id: str,
    patch: MeetingUpdate,
    service: MeetingIngestionService = Depends(get_ingestion_service),
    db: Session = Depends(get_db),
):
    try:
        result = service.update(meeting_id, patch)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.delete("/{meeting_id}", status_code=204)
def delete_meeting(
    meeting_id: str,
    service: MeetingIngestionService = Depends(get_ingestion_service),
    db: Session = Depends(get_db),
):
    try:
        service.delete(meeting_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
