"""
Contact section endpoints — Gmail / Outlook / Teams / Calendar via Composio.

Every handler degrades gracefully: if Composio isn't configured or a call
fails, a clear message is returned instead of a 500, so the UI can guide the
user (e.g. "set COMPOSIO_API_KEY", "connect Gmail in the Composio dashboard").
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_composio_service, get_report_service
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.comms_schema import (
    CommsResult,
    CommsStatus,
    ExecuteRequest,
    SendEmailRequest,
)
from app.services.integrations.composio_service import ComposioError, ComposioService
from app.services.reporting.report_service import ReportService

router = APIRouter(prefix="/comms", tags=["contact"])


class SendMeetingRequest(BaseModel):
    to: str = Field(..., examples=["boss@example.com"])
    provider: str = Field(default="gmail", examples=["gmail", "outlook"])
    subject: str | None = None
    message: str | None = None


@router.get("/status", response_model=CommsStatus)
def status(svc: ComposioService = Depends(get_composio_service)):
    if not svc.enabled:
        return CommsStatus(
            enabled=False,
            entity_id=svc.settings.composio_entity_id,
            error="Composio not configured. Set COMPOSIO_API_KEY in backend/.env.",
        )
    try:
        return CommsStatus(
            enabled=True,
            entity_id=svc.settings.composio_entity_id,
            connections=svc.connections(),
        )
    except ComposioError as exc:
        return CommsStatus(
            enabled=True,
            entity_id=svc.settings.composio_entity_id,
            error=str(exc),
        )


@router.get("/actions")
def actions(
    app: str = Query(..., examples=["gmail", "outlook", "microsoft_teams"]),
    svc: ComposioService = Depends(get_composio_service),
):
    try:
        return {"app": app, "actions": svc.actions(app)}
    except ComposioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/emails", response_model=CommsResult)
def emails(
    provider: str = Query(default="gmail"),
    limit: int = Query(default=10, ge=1, le=50),
    svc: ComposioService = Depends(get_composio_service),
):
    try:
        return svc.fetch_emails(provider, limit)
    except ComposioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/send", response_model=CommsResult)
def send(
    req: SendEmailRequest, svc: ComposioService = Depends(get_composio_service)
):
    try:
        return svc.send_email(req.provider, req.to, req.subject, req.body)
    except ComposioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/events", response_model=CommsResult)
def events(
    provider: str = Query(default="gmail"),
    limit: int = Query(default=10, ge=1, le=50),
    svc: ComposioService = Depends(get_composio_service),
):
    try:
        return svc.list_events(provider, limit)
    except ComposioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execute", response_model=CommsResult)
def execute(
    req: ExecuteRequest, svc: ComposioService = Depends(get_composio_service)
):
    try:
        return svc.execute(
            req.action, req.params, connected_account_id=req.connected_account_id
        )
    except ComposioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/send-meeting/{meeting_id}", response_model=CommsResult)
def send_meeting(
    meeting_id: str,
    req: SendMeetingRequest,
    svc: ComposioService = Depends(get_composio_service),
    report_svc: ReportService = Depends(get_report_service),
    db: Session = Depends(get_db),
):
    """Email a meeting's details directly via Composio as a PDF (no Hermes)."""
    meeting = MeetingRepository(db).get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    report = report_svc.meeting_report(meeting_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Meeting report not found")

    from pathlib import Path
    from app.core.config import get_settings

    pdf = report_svc.render_pdf(report)
    settings = get_settings()
    out_dir = Path(settings.reports_dir or (Path.home() / "governance-reports"))
    filename = f"management-report-{meeting_id}.pdf"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / filename
        path.write_bytes(pdf)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not write the PDF to '{out_dir}': {exc}",
        ) from exc

    body = req.message or f"Please find attached the meeting details/report for {meeting.title}."
    subject = req.subject or f"Meeting details: {meeting.title}"
    try:
        return svc.send_email(req.provider, req.to, subject, body, attachment=str(path))
    except ComposioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
