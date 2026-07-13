"""
Report endpoints.

  GET /reports/meeting/{id}            -> PDF download (per meeting)
  GET /reports/meeting/{id}/preview    -> JSON preview
  GET /reports/weekly?date=YYYY-MM-DD  -> PDF download (week containing date)
  GET /reports/weekly/preview?date=... -> JSON preview

`date` is optional and defaults to today (current week).
"""
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.database import get_db
from app.models.auto_send_settings import AutoSendSettings
from app.core.dependencies import (
    get_composio_service,
    get_hermes_control_service,
    get_report_service,
)
from app.schemas.report_schema import ProjectReport
from app.services.hermes.control_service import (
    HermesControlError,
    HermesControlService,
)
from app.services.integrations.composio_service import (
    ComposioError,
    ComposioService,
)
from app.services.reporting.report_service import ReportService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/reports", tags=["reports"])


class AutoSendSettingsRequest(BaseModel):
    enabled: bool
    target_email: str
    email_provider: str = "gmail"


@router.get("/settings")
def get_auto_send_settings(db: Session = Depends(get_db)):
    settings = db.query(AutoSendSettings).first()
    if not settings:
        settings = AutoSendSettings(enabled=False, target_email="", email_provider="gmail")
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return {
        "enabled": settings.enabled,
        "target_email": settings.target_email,
        "email_provider": settings.email_provider,
    }


@router.post("/settings")
def update_auto_send_settings(req: AutoSendSettingsRequest, db: Session = Depends(get_db)):
    settings = db.query(AutoSendSettings).first()
    if not settings:
        settings = AutoSendSettings()
        db.add(settings)
    settings.enabled = req.enabled
    settings.target_email = req.target_email
    settings.email_provider = req.email_provider
    db.commit()
    db.refresh(settings)
    return {
        "enabled": settings.enabled,
        "target_email": settings.target_email,
        "email_provider": settings.email_provider,
    }


class EmailReportRequest(BaseModel):
    scope: str = Field(default="meeting", examples=["meeting", "project", "weekly"])
    meeting_id: str | None = None
    project_id: int | None = None
    date: str | None = None
    to: str = Field(..., examples=["someone@example.com"])
    subject: str | None = None
    message: str | None = None
    via: str = Field(default="composio", examples=["composio", "hermes"])
    email_provider: str = Field(default="gmail", examples=["gmail", "outlook"])
    gstack: bool = False


def _pdf_response(pdf: bytes, filename: str) -> Response:
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/meeting/{meeting_id}/preview", response_model=ProjectReport)
def meeting_preview(
    meeting_id: str, service: ReportService = Depends(get_report_service)
):
    report = service.meeting_report(meeting_id)
    if not report:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return report


@router.get("/meeting/{meeting_id}")
def meeting_pdf(
    meeting_id: str, service: ReportService = Depends(get_report_service)
):
    report = service.meeting_report(meeting_id)
    if not report:
        raise HTTPException(status_code=404, detail="Meeting not found")
    pdf = service.render_pdf(report)
    return _pdf_response(pdf, f"report_{meeting_id}.pdf")


@router.get("/weekly/preview", response_model=ProjectReport)
def weekly_preview(
    date_: date | None = Query(default=None, alias="date"),
    service: ReportService = Depends(get_report_service),
):
    return service.weekly_report(date_ or date.today())


@router.get("/weekly")
def weekly_pdf(
    date_: date | None = Query(default=None, alias="date"),
    service: ReportService = Depends(get_report_service),
):
    day = date_ or date.today()
    report = service.weekly_report(day)
    pdf = service.render_pdf(report)
    iso = report.period_start.isoformat() if report.period_start else day.isoformat()
    return _pdf_response(pdf, f"weekly_report_{iso}.pdf")


@router.get("/project/{project_id}/preview", response_model=ProjectReport)
def project_preview(
    project_id: int, service: ReportService = Depends(get_report_service)
):
    return service.project_report(project_id)


@router.get("/project/{project_id}")
def project_pdf(
    project_id: int, service: ReportService = Depends(get_report_service)
):
    report = service.project_report(project_id)
    pdf = service.render_pdf(report)
    return _pdf_response(pdf, f"project_{project_id}_report.pdf")


@router.post("/email")
def email_report(
    req: EmailReportRequest,
    service: ReportService = Depends(get_report_service),
    ctrl: HermesControlService = Depends(get_hermes_control_service),
    composio: ComposioService = Depends(get_composio_service),
):
    """Generate a management report PDF and email it as an attachment.

    `via="composio"` (default) sends directly through your connected Composio
    account with the PDF attached — no Hermes involved. `via="hermes"` uses
    `hermes send` instead.
    """
    scope = (req.scope or "meeting").lower()
    if scope == "meeting":
        if not req.meeting_id:
            raise HTTPException(status_code=400, detail="meeting_id is required")
        report = service.meeting_report(req.meeting_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Meeting not found")
        filename = f"management-report-{req.meeting_id}.pdf"
    elif scope == "project":
        if req.project_id is None:
            raise HTTPException(status_code=400, detail="project_id is required")
        report = service.project_report(req.project_id)
        filename = f"management-report-project-{req.project_id}.pdf"
    elif scope == "weekly":
        day = date.fromisoformat(req.date) if req.date else date.today()
        report = service.weekly_report(day)
        filename = f"management-report-weekly-{day.isoformat()}.pdf"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scope '{scope}'")

    if req.gstack:
        scope_id = req.meeting_id if scope == "meeting" else (f"project_{req.project_id}" if scope == "project" else f"weekly_{day.isoformat()}")
        pdf = _render_gstack_pdf(report, scope_id, service)
    else:
        pdf = service.render_pdf(report)
    settings = get_settings()
    out_dir = Path(settings.reports_dir or (Path.home() / "governance-reports"))
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / filename
        path.write_bytes(pdf)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not write the PDF to '{out_dir}': {exc}",
        ) from exc

    subject = req.subject or f"Management report: {report.scope_label}"
    body = req.message or (
        f"Please find attached the management report for {report.scope_label}."
    )

    via = (req.via or "composio").lower()
    if via == "composio":
        try:
            result = composio.send_email(
                req.email_provider, req.to, subject, body, attachment=str(path)
            )
        except ComposioError as exc:
            return {
                "ok": False,
                "via": "composio",
                "file": str(path),
                "to": req.to,
                "output": (
                    f"PDF generated at {path}, but the Composio send failed: {exc}. "
                    f"You can still download it from the report's Download button."
                ),
            }
        return {
            "ok": True,
            "via": "composio",
            "file": str(path),
            "to": req.to,
            "output": f"Sent via Composio ({req.email_provider}) to {req.to} with the PDF attached.",
            "raw": result.get("data"),
        }

    # via == "hermes"
    try:
        result = ctrl.email_file(req.to, subject, body, str(path))
    except HermesControlError as exc:
        return {
            "ok": False,
            "via": "hermes",
            "file": str(path),
            "to": req.to,
            "output": (
                f"PDF generated at {path}, but Hermes could not send it ({exc}). "
                f"You can still download it from the report's Download button."
            ),
        }
    result["file"] = str(path)
    result["via"] = "hermes"
    return result


class RunSkillRequest(BaseModel):
    skill_name: str
    meeting_id: str


@router.post("/run-skill")
def run_skill(
    req: RunSkillRequest,
    db: Session = Depends(get_db),
):
    from app.core.dependencies import get_gstack_service
    from app.repositories.meeting_repository import MeetingRepository
    from app.services.reporting.pdf_renderer import render_markdown_to_pdf

    meeting = MeetingRepository(db).get(req.meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    transcript = meeting.raw_transcript
    if not transcript or not transcript.strip():
        raise HTTPException(status_code=400, detail="Meeting has no transcript")

    gstack = get_gstack_service()
    try:
        res = gstack.run_skill_on_transcript(req.skill_name, transcript)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not res.get("ok", False):
        raise HTTPException(status_code=500, detail=res.get("output", "Hermes skill execution failed"))

    markdown_content = res.get("output", "")

    # Save the generated PDF bytes to the reports directory
    settings = get_settings()
    reports_dir = Path(settings.reports_dir or (Path.home() / "governance-reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)

    pdf_filename = f"management-report-{req.skill_name}-{req.meeting_id}.pdf"
    pdf_path = reports_dir / pdf_filename

    try:
        title = f"{req.skill_name.upper()} Report: {meeting.title}"
        pdf_bytes = render_markdown_to_pdf(title, markdown_content)
        pdf_path.write_bytes(pdf_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {exc}")

    return {
        "ok": True,
        "markdown": markdown_content,
        "pdf_url": f"/reports/skills/download?skill_name={req.skill_name}&meeting_id={req.meeting_id}"
    }


@router.get("/skills/download")
def download_skill_report(
    skill_name: str,
    meeting_id: str,
):
    settings = get_settings()
    reports_dir = Path(settings.reports_dir or (Path.home() / "governance-reports"))
    pdf_filename = f"management-report-{skill_name}-{meeting_id}.pdf"
    pdf_path = reports_dir / pdf_filename

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF report not found")

    try:
        pdf_bytes = pdf_path.read_bytes()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read PDF: {exc}")

    return _pdf_response(pdf_bytes, pdf_filename)


def _format_report_markdown(report) -> str:
    content = f"# Retrospective Report: {report.title}\n"
    content += f"Scope: {report.scope_label}\n"
    content += f"Provider: {report.provider}\n\n"
    content += f"## Executive Summary\n{report.executive_summary}\n\n"
    
    if report.merits:
        content += "## Merits — What went well\n"
        for m in report.merits:
            evidence = f" (Evidence: {m.evidence})" if m.evidence else ""
            source = f" [{m.source}]" if m.source else ""
            content += f"- {m.text}{evidence}{source}\n"
        content += "\n"
        
    if report.demerits:
        content += "## Demerits — Risks & blockers\n"
        for d in report.demerits:
            evidence = f" (Evidence: {d.evidence})" if d.evidence else ""
            source = f" [{d.source}]" if d.source else ""
            content += f"- {d.text}{evidence}{source}\n"
        content += "\n"
        
    if report.action_items:
        content += "## Action Items\n"
        for a in report.action_items:
            due = f" (due {a.due})" if a.due else ""
            content += f"- {a.owner or 'unassigned'}: {a.task}{due} [{a.status}]\n"
        content += "\n"
    return content


def _render_gstack_pdf(report, scope_id: str, service) -> bytes:
    from app.core.dependencies import get_gstack_service
    
    try:
        gstack = get_gstack_service()
        if gstack.settings.gstack_dir:
            content = _format_report_markdown(report)
            res = gstack.run_skill("make-pdf", scope_id, report.title, content)
            pdf_path = res.get("produced_file")
            if pdf_path and Path(pdf_path).exists():
                return Path(pdf_path).read_bytes()
    except Exception:
        pass
        
    return service.render_pdf(report)


@router.get("/meeting/{meeting_id}/gstack")
def meeting_gstack_pdf(
    meeting_id: str,
    service: ReportService = Depends(get_report_service),
):
    report = service.meeting_report(meeting_id)
    if not report:
        raise HTTPException(status_code=404, detail="Meeting not found")
    pdf = _render_gstack_pdf(report, meeting_id, service)
    return _pdf_response(pdf, f"gstack_report_{meeting_id}.pdf")


@router.get("/project/{project_id}/gstack")
def project_gstack_pdf(
    project_id: int,
    service: ReportService = Depends(get_report_service),
):
    report = service.project_report(project_id)
    if not report:
        raise HTTPException(status_code=404, detail="Project not found")
    pdf = _render_gstack_pdf(report, f"project_{project_id}", service)
    return _pdf_response(pdf, f"gstack_report_project_{project_id}.pdf")


@router.get("/weekly/gstack")
def weekly_gstack_pdf(
    date_: date | None = Query(default=None, alias="date"),
    service: ReportService = Depends(get_report_service),
):
    day = date_ or date.today()
    report = service.weekly_report(day)
    pdf = _render_gstack_pdf(report, f"weekly_{day.isoformat()}", service)
    return _pdf_response(pdf, f"gstack_report_weekly_{day.isoformat()}.pdf")



