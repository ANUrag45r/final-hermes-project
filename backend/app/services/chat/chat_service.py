"""
Chat orchestration (Stages 8-9).

Wires retrieval to reasoning:
  GBrain.search -> RAGContext -> Hermes.answer -> ChatResponse

It depends on the GBrain and Hermes interfaces only, never on concrete
implementations, keeping retrieval and reasoning cleanly separated.
"""
import re

from app.repositories.meeting_repository import MeetingRepository
from app.schemas.chat_schema import ChatRequest, ChatResponse, RAGContext
from app.services.gbrain.base import AbstractGBrain
from app.services.hermes.hermes_service import HermesService
from app.services.integrations.mail_service import MailService
from app.services.reporting.report_service import ReportService
from app.utils.logger import get_logger

logger = get_logger("chat")

_PROJECT_RE = re.compile(r"\bproject\s+(?:id\s+)?(\d+)\b", re.IGNORECASE)
_DIGEST_RE = re.compile(
    r"\b(status|digest|current state|where (do |does )?.*stand|overview|"
    r"summary|standing|state of|how('?s| is) .* (going|progressing))\b",
    re.IGNORECASE,
)


class ChatService:
    def __init__(
        self,
        gbrain: AbstractGBrain,
        hermes: HermesService,
        mail: MailService | None = None,
        meeting_repo: MeetingRepository | None = None,
        reports: ReportService | None = None,
    ) -> None:
        self.gbrain = gbrain
        self.hermes = hermes
        self.mail = mail
        self.meeting_repo = meeting_repo
        self.reports = reports

    def _resolve_project(self, request: ChatRequest) -> int | None:
        if request.project_id is not None:
            return request.project_id
        m = _PROJECT_RE.search(request.query)
        return int(m.group(1)) if m else None

    def ask(self, request: ChatRequest) -> ChatResponse:
        project_id = self._resolve_project(request)

        # Project-status digest: "give me project 1's current state", "status",
        # "overview", etc. Handled by the app's report engine (its own data),
        # so it works even in agentic mode.
        if self.reports is not None and _DIGEST_RE.search(request.query):
            report = (
                self.reports.project_report(project_id)
                if project_id is not None
                else self.reports.all_report()
            )
            if report.stats.meetings > 0:
                return ChatResponse(
                    answer=self.reports.digest_text(report),
                    context=RAGContext(query=request.query),
                    provider="digest",
                    action="digest",
                )

        # Agentic Hermes (its own gbrain + composio mail + tools): pass the
        # question through untouched and return Hermes's answer directly.
        if self.hermes.agentic:
            answer = self.hermes.answer_raw(request.query)
            return ChatResponse(
                answer=answer,
                context=RAGContext(query=request.query),
                provider=self.hermes.provider,
                action="rag",
            )

        # 0. Mail / Teams intents take priority (e.g. "fetch my last 3 mails").
        if self.mail is not None:
            mail_result = self.mail.handle(request.query)
            if mail_result is not None:
                return ChatResponse(
                    answer=mail_result.answer,
                    context=RAGContext(query=request.query),
                    provider="outlook",
                    action=mail_result.action,
                    emails=[e.model_dump() for e in (mail_result.emails or [])]
                    if mail_result.emails is not None
                    else None,
                )

        # Resolve a project scope to a set of meeting ids.
        meeting_ids: list[str] | None = None
        if project_id is not None and self.meeting_repo is not None:
            meeting_ids = self.meeting_repo.meeting_ids_for_project(project_id)
            logger.info(
                "Scoping retrieval to project %s (%d meetings)",
                project_id, len(meeting_ids),
            )

        # Stage 8: retrieve evidence (graph + vector fusion), scoped if asked.
        context = self.gbrain.search(
            request.query,
            meeting_id=request.meeting_id,
            top_k=request.top_k,
            meeting_ids=meeting_ids,
        )
        # Stage 9: reason over the evidence.
        answer = self.hermes.answer(request.query, context)
        return ChatResponse(
            answer=answer, context=context, provider=self.hermes.provider
        )
