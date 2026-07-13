"""
Mail service.

Wraps the Graph client with (a) graceful handling when credentials are absent
and (b) lightweight natural-language intent parsing so the chat box can drive
Outlook: "fetch my last 3 mails", "send an email to sam@x.com saying ...".

If Microsoft Graph is not configured, mail intents return a helpful setup
message instead of failing — the rest of the app keeps working.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import Settings
from app.services.integrations.base import EmailSummary, NotConfiguredError
from app.services.integrations.graph_client import MicrosoftGraphClient
from app.utils.logger import get_logger

logger = get_logger("mail")

_FETCH_RE = re.compile(
    r"\b(fetch|show|get|read|check|list|pull)\b.*\b(mail|mails|email|emails|inbox|messages?)\b",
    re.IGNORECASE,
)
_SEND_RE = re.compile(
    r"\b(send|write|compose|email|mail)\b.*\bto\b\s+(?P<to>[^\s,]+)",
    re.IGNORECASE,
)
_COUNT_RE = re.compile(r"\b(?:last|recent|latest|top)\s+(\d{1,2})\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


@dataclass
class MailResult:
    answer: str
    action: str  # "mail_fetch" | "mail_send" | "mail_help"
    emails: list[EmailSummary] | None = None


class MailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: MicrosoftGraphClient | None = None
        self._reason = ""
        try:
            self._client = MicrosoftGraphClient(settings)
        except NotConfiguredError as exc:
            self._reason = str(exc)

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    # --- intent routing -------------------------------------------------
    def detect(self, text: str) -> str | None:
        if _SEND_RE.search(text):
            return "send"
        if _FETCH_RE.search(text):
            return "fetch"
        return None

    def handle(self, text: str) -> MailResult | None:
        intent = self.detect(text)
        if not intent:
            return None
        if not self.is_configured:
            return MailResult(
                answer=(
                    "Email isn't connected yet. Add your Microsoft 365 credentials "
                    "to the .env file (GRAPH_TENANT_ID, GRAPH_CLIENT_ID, "
                    "GRAPH_CLIENT_SECRET, GRAPH_DEFAULT_USER) and restart. "
                    f"({self._reason})"
                ),
                action="mail_help",
            )
        return self._fetch(text) if intent == "fetch" else self._send(text)

    # --- handlers -------------------------------------------------------
    def _fetch(self, text: str) -> MailResult:
        m = _COUNT_RE.search(text)
        count = int(m.group(1)) if m else 3
        try:
            emails = self._client.list_recent(count)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            logger.error("Mail fetch failed: %s", exc)
            return MailResult(answer=f"Couldn't fetch mail: {exc}", action="mail_help")

        if not emails:
            return MailResult(answer="Your inbox looks empty.", action="mail_fetch", emails=[])

        lines = [f"Here are your last {len(emails)} email(s):", ""]
        for i, e in enumerate(emails, 1):
            lines.append(f"{i}. {e.subject} — from {e.sender}")
            if e.preview:
                lines.append(f"   {e.preview[:140]}")
        return MailResult(answer="\n".join(lines), action="mail_fetch", emails=emails)

    def _send(self, text: str) -> MailResult:
        recipient = self._parse_recipient(text)
        if not recipient:
            return MailResult(
                answer="Who should I send it to? Include an address, e.g. "
                '"send an email to sam@example.com saying ...".',
                action="mail_help",
            )
        subject, body = self._parse_subject_body(text)
        if not body:
            return MailResult(
                answer=f"What should the email to {recipient} say? Add it after "
                '"saying" or "body:".',
                action="mail_help",
            )
        try:
            self._client.send(recipient, subject, body)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            logger.error("Mail send failed: %s", exc)
            return MailResult(answer=f"Couldn't send the email: {exc}", action="mail_help")
        return MailResult(
            answer=f'Sent to {recipient} with subject "{subject}".',
            action="mail_send",
        )

    # --- parsing helpers ------------------------------------------------
    @staticmethod
    def _parse_recipient(text: str) -> str | None:
        m = _EMAIL_RE.search(text)
        return m.group(0) if m else None

    @staticmethod
    def _parse_subject_body(text: str) -> tuple[str, str]:
        subject = "Message from Governance Brain"
        sm = re.search(r"subject:\s*(.+?)(?:\s+(?:saying|body:|that says|-)|$)", text, re.I)
        if sm:
            subject = sm.group(1).strip()
        bm = re.search(r"(?:saying|body:|that says|message:|:)\s*(.+)$", text, re.I)
        body = bm.group(1).strip() if bm else ""
        if body and not sm:
            subject = (body[:60] + "…") if len(body) > 60 else body
        return subject, body
