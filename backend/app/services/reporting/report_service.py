"""
Report service — orchestration.

Builds the structured report, optionally enriches the executive summary with
Hermes when a real LLM is configured (the offline `local` reasoner keeps the
deterministic summary), and renders the PDF.
"""
from datetime import date

import json
import re
from app.schemas.chat_schema import GraphFact, RAGContext, VectorHit
from app.schemas.report_schema import ProjectReport, Insight, ActionItemRef
from app.services.hermes.hermes_service import HermesService
from app.services.hermes.gstack_service import GStackService
from app.services.reporting.pdf_renderer import render_report
from app.services.reporting.report_builder import ReportBuilder
from app.utils.logger import get_logger

logger = get_logger("reporting")


class ReportService:
    def __init__(self, builder: ReportBuilder, hermes: HermesService, gstack: GStackService) -> None:
        self.builder = builder
        self.hermes = hermes
        self.gstack = gstack

    def meeting_report(self, meeting_id: str) -> ProjectReport | None:
        report = self.builder.for_meeting(meeting_id)
        return self._enrich(report) if report else None

    def weekly_report(self, any_day: date) -> ProjectReport:
        return self._enrich(self.builder.for_week(any_day))

    def project_report(self, project_id: int) -> ProjectReport:
        return self._enrich(self.builder.for_project(project_id))

    def all_report(self) -> ProjectReport:
        return self._enrich(self.builder.for_all())

    def render_pdf(self, report: ProjectReport) -> bytes:
        return render_report(report)

    @staticmethod
    def digest_text(report: ProjectReport) -> str:
        """A concise, chat-friendly status digest from a built report."""
        s = report.stats
        lines = [
            f"{report.scope_label} — status digest "
            f"({s.meetings} meeting(s), {s.people} people, "
            f"{s.done_action_items} done / {s.open_action_items} open)",
            "",
        ]
        if report.responsibilities:
            lines.append("Owners:")
            for r in report.responsibilities:
                lines.append(f"  - {r.owner}: {', '.join(r.tasks)}")
            lines.append("")
        open_items = [a for a in report.action_items if a.status == "open"]
        if open_items:
            lines.append("Open action items:")
            for a in open_items[:12]:
                due = f" (due {a.due})" if a.due else ""
                who = a.owner or "unassigned"
                lines.append(f"  - {who} — {a.task}{due}")
            lines.append("")
        risks = [d for d in report.demerits if "No blockers" not in d.text]
        if risks:
            lines.append("Risks / blockers:")
            for d in risks[:8]:
                lines.append(f"  - {d.text}")
            lines.append("")
        wins = [m for m in report.merits if "No explicit" not in m.text]
        if wins:
            lines.append("Recent progress:")
            for m in wins[:6]:
                lines.append(f"  - {m.text}")
        return "\n".join(lines).strip()

    # --- optional LLM enrichment ---------------------------------------
    def _enrich(self, report: ProjectReport) -> ProjectReport:
        if self.hermes.provider == "local":
            return report  # keep the deterministic summary

        # 1. Retrieve all meeting transcripts in the report scope and combine them
        meeting_ids = [m.meeting_id for m in report.meetings]
        transcripts = []
        for mid in meeting_ids:
            m_obj = self.builder.repo.meeting(mid)
            if m_obj and m_obj.raw_transcript:
                transcripts.append(f"Meeting {m_obj.meeting_id} - {m_obj.title}:\n{m_obj.raw_transcript.strip()}")
        combined_transcript = "\n\n".join(transcripts)

        if combined_transcript.strip():
            try:
                # 2. Load /retro skill instructions from GStack
                instructions = self.gstack.load_skill_instructions("retro")
                
                # 3. Prompt Hermes with /retro skill guidelines to return JSON
                prompt = (
                    f"Use the GStack retrospective skill ('/retro') to compile a sprint retrospective report from the meeting transcripts below.\n\n"
                    f"Skill Instructions:\n{instructions}\n\n"
                    f"MEETING TRANSCRIPTS:\n{combined_transcript}\n\n"
                    f"You MUST respond ONLY with a raw JSON object matching the schema below. Do not wrap the JSON in Markdown code blocks (like ```json), do not include any other conversational text or preamble. Output raw JSON ONLY.\n\n"
                    f"JSON SCHEMA:\n"
                    f"{{\n"
                    f"  \"executive_summary\": \"A high-level executive summary of the overall status (string)\",\n"
                    f"  \"merits\": [\n"
                    f"    {{\"text\": \"Win/achievement description\", \"evidence\": \"Quote or specific detail from transcript\", \"source\": \"Person who mentioned it or None\"}}\n"
                    f"  ],\n"
                    f"  \"demerits\": [\n"
                    f"    {{\"text\": \"Risk/blocker description\", \"evidence\": \"Quote or specific detail\", \"source\": \"Person or None\"}}\n"
                    f"  ],\n"
                    f"  \"action_items\": [\n"
                    f"    {{\"owner\": \"Person name or None\", \"task\": \"Action item description\", \"due\": \"Due date or None\", \"status\": \"open\"}}\n"
                    f"  ]\n"
                    f"}}\n"
                )
                
                response = self.hermes.answer_raw(prompt)
                
                # Clean response
                cleaned_text = response.strip()
                if cleaned_text.startswith("```"):
                    cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text)
                    cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
                cleaned_text = cleaned_text.strip()
                
                # Parse JSON
                data = json.loads(cleaned_text)
                if isinstance(data, dict):
                    if "executive_summary" in data and isinstance(data["executive_summary"], str):
                        report.executive_summary = data["executive_summary"].strip()
                    
                    if "merits" in data and isinstance(data["merits"], list):
                        report.merits = [
                            Insight(
                                text=item.get("text", ""),
                                evidence=item.get("evidence"),
                                source=item.get("source")
                            )
                            for item in data["merits"]
                            if isinstance(item, dict) and item.get("text")
                        ]
                        
                    if "demerits" in data and isinstance(data["demerits"], list):
                        report.demerits = [
                            Insight(
                                text=item.get("text", ""),
                                evidence=item.get("evidence"),
                                source=item.get("source")
                            )
                            for item in data["demerits"]
                            if isinstance(item, dict) and item.get("text")
                        ]
                        
                    if "action_items" in data and isinstance(data["action_items"], list):
                        report.action_items = [
                            ActionItemRef(
                                owner=item.get("owner"),
                                task=item.get("task", ""),
                                due=item.get("due"),
                                status=item.get("status", "open"),
                                meeting_id=meeting_ids[0] if meeting_ids else "unknown"
                            )
                            for item in data["action_items"]
                            if isinstance(item, dict) and item.get("task")
                        ]
                    
                    report.provider = self.hermes.provider
                    return report
            except Exception as exc:
                logger.error("GStack /retro JSON enrichment failed, falling back to standard RAG: %s", exc)

        # Fallback to standard RAG/heuristics
        try:
            context = RAGContext(
                query="Summarize project status, merits and risks for this report.",
                graph_facts=[
                    GraphFact(source=r.owner, relation="responsible_for", target=t)
                    for r in report.responsibilities
                    for t in r.tasks
                ],
                vector_hits=[
                    VectorHit(content=i.evidence or i.text, speaker=i.source)
                    for i in (report.merits + report.demerits)
                    if i.evidence or i.text
                ][:8],
            )
            summary = self.hermes.answer(context.query, context)
            if summary.strip():
                report.executive_summary = summary.strip()
                report.provider = self.hermes.provider
        except Exception as exc:  # noqa: BLE001
            logger.error("Report enrichment failed, keeping deterministic summary: %s", exc)
        return report
