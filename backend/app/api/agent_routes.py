"""Hermes Agent panel endpoints — read-only CLI monitoring + CLI chat."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    get_gstack_service,
    get_hermes_control_service,
    get_report_service,
)
from app.repositories.meeting_repository import MeetingRepository
from app.services.hermes.control_service import (
    HermesControlError,
    HermesControlService,
)
from app.services.hermes.gstack_service import GStackService
from app.services.reporting.report_service import ReportService

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentChatRequest(BaseModel):
    message: str = Field(..., examples=["give my last 3 mails"])


class RunSkillRequest(BaseModel):
    skill_id: str = Field(..., examples=["make-pdf"])
    meeting_id: str


@router.get("/status")
def status(svc: HermesControlService = Depends(get_hermes_control_service)):
    return {
        "available": svc.available(),
        "cli_path": svc.settings.hermes_cli_path or "hermes (PATH)",
        "actions": svc.actions,
    }


@router.get("/run/{action}")
def run(
    action: str, svc: HermesControlService = Depends(get_hermes_control_service)
):
    try:
        return svc.run(action)
    except HermesControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat")
def chat(
    req: AgentChatRequest,
    svc: HermesControlService = Depends(get_hermes_control_service),
):
    """Send a message straight to the Hermes CLI and return its output."""
    try:
        return svc.chat(req.message)
    except HermesControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/save-meeting/{meeting_id}")
def save_meeting_to_gbrain(
    meeting_id: str,
    svc: HermesControlService = Depends(get_hermes_control_service),
    db: Session = Depends(get_db),
):
    """Command Hermes to store a specific meeting in its gbrain memory."""
    meeting = MeetingRepository(db).get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    try:
        return svc.save_to_gbrain(
            meeting.meeting_id, meeting.title, meeting.raw_transcript
        )
    except HermesControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/skills")
def list_skills(svc: GStackService = Depends(get_gstack_service)):
    """Curated meeting skills + the full installed-skills catalogue."""
    try:
        installed = svc.list_installed()
    except HermesControlError:
        installed = []  # CLI not available — still return curated set
    return {"curated": svc.curated, "installed": installed}


@router.post("/skills/run")
def run_skill(
    req: RunSkillRequest,
    svc: GStackService = Depends(get_gstack_service),
    report_svc: ReportService = Depends(get_report_service),
    db: Session = Depends(get_db),
):
    """Run a gstack skill against a meeting's content via Hermes."""
    meeting = MeetingRepository(db).get(req.meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Build the content the skill operates on: a structured digest + transcript.
    report = report_svc.meeting_report(req.meeting_id)
    lines = [f"Title: {meeting.title}", f"Meeting ID: {meeting.meeting_id}", ""]
    if report is not None:
        if report.merits:
            lines.append("Highlights:")
            lines += [f"- {m.text}" for m in report.merits]
        if report.demerits:
            lines.append("Risks / blockers:")
            lines += [f"- {d.text}" for d in report.demerits]
        if report.action_items:
            lines.append("Action items:")
            lines += [
                f"- {a.task} (owner: {a.owner or 'unassigned'})"
                for a in report.action_items
            ]
    lines += ["", "Transcript:", meeting.raw_transcript or ""]
    content = "\n".join(lines)

    try:
        return svc.run_skill(req.skill_id, meeting.meeting_id, meeting.title, content)
    except HermesControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class AutoplanRequest(BaseModel):
    meeting_id: str


@router.post("/autoplan")
def run_autoplan(
    req: AutoplanRequest,
    svc: GStackService = Depends(get_gstack_service),
    report_svc: ReportService = Depends(get_report_service),
    db: Session = Depends(get_db),
):
    """Run sequential CEO, Design, Eng, and DX reviews against a meeting."""
    meeting = MeetingRepository(db).get(req.meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Build the content the reviews operate on (same as run_skill)
    report = report_svc.meeting_report(req.meeting_id)
    lines = [f"Title: {meeting.title}", f"Meeting ID: {meeting.meeting_id}", ""]
    if report is not None:
        if report.merits:
            lines.append("Highlights:")
            lines += [f"- {m.text}" for m in report.merits]
        if report.demerits:
            lines.append("Risks / blockers:")
            lines += [f"- {d.text}" for d in report.demerits]
        if report.action_items:
            lines.append("Action items:")
            lines += [
                f"- {a.task} (owner: {a.owner or 'unassigned'})"
                for a in report.action_items
            ]
    lines += ["", "Transcript:", meeting.raw_transcript or ""]
    content = "\n".join(lines)

    try:
        return svc.run_autoplan(meeting.meeting_id, meeting.title, content)
    except HermesControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
