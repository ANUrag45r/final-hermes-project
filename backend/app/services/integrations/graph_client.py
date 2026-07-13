"""
Microsoft Graph client (Outlook mail + Teams).

Authenticates with the OAuth2 client-credentials flow via MSAL using the Azure
AD app registration configured in `.env`. All secrets come from Settings; none
are hard-coded.

Required Azure AD application permissions (with admin consent):
  - Mail.Read   (read the mailbox)
  - Mail.Send   (send as the mailbox)
  - Chat.ReadWrite / ChannelMessage.Send  (for Teams, optional)
"""
from __future__ import annotations

import httpx

from app.core.config import Settings
from app.services.integrations.base import EmailSummary, NotConfiguredError
from app.utils.logger import get_logger

logger = get_logger("graph")

GRAPH = "https://graph.microsoft.com/v1.0"
AUTHORITY = "https://login.microsoftonline.com"
SCOPE = ["https://graph.microsoft.com/.default"]


class MicrosoftGraphClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.graph_enabled:
            raise NotConfiguredError(
                "Microsoft Graph is not configured. Set GRAPH_TENANT_ID, "
                "GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET and GRAPH_DEFAULT_USER."
            )
        self.user = settings.graph_default_user
        self._tenant = settings.graph_tenant_id
        self._client_id = settings.graph_client_id
        self._secret = settings.graph_client_secret
        self._timeout = 30.0

    # --- auth -----------------------------------------------------------
    def _token(self) -> str:
        # Imported lazily so the dependency is only needed when mail is used.
        import msal

        app = msal.ConfidentialClientApplication(
            client_id=self._client_id,
            client_credential=self._secret,
            authority=f"{AUTHORITY}/{self._tenant}",
        )
        result = app.acquire_token_for_client(scopes=SCOPE)
        if "access_token" not in result:
            raise NotConfiguredError(
                f"Graph auth failed: {result.get('error_description', 'unknown error')}"
            )
        return result["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": "application/json",
        }

    # --- Outlook mail ---------------------------------------------------
    def list_recent(self, count: int = 3) -> list[EmailSummary]:
        params = {
            "$top": str(max(1, min(count, 25))),
            "$select": "from,subject,receivedDateTime,bodyPreview",
            "$orderby": "receivedDateTime desc",
        }
        resp = httpx.get(
            f"{GRAPH}/users/{self.user}/mailFolders/inbox/messages",
            headers=self._headers(),
            params=params,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        out: list[EmailSummary] = []
        for m in resp.json().get("value", []):
            addr = (m.get("from") or {}).get("emailAddress") or {}
            out.append(
                EmailSummary(
                    id=m.get("id", ""),
                    sender=addr.get("address") or addr.get("name") or "unknown",
                    subject=m.get("subject") or "(no subject)",
                    received=m.get("receivedDateTime", ""),
                    preview=(m.get("bodyPreview") or "").strip()[:200],
                )
            )
        return out

    def send(self, to: str, subject: str, body: str) -> None:
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": True,
        }
        resp = httpx.post(
            f"{GRAPH}/users/{self.user}/sendMail",
            headers=self._headers(),
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        logger.info("Sent mail to %s", to)

    # --- Teams (optional) ----------------------------------------------
    def send_chat_message(self, chat_id: str, text: str) -> None:
        resp = httpx.post(
            f"{GRAPH}/chats/{chat_id}/messages",
            headers=self._headers(),
            json={"body": {"content": text}},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        logger.info("Sent Teams message to chat %s", chat_id)
