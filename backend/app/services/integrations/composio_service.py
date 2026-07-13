"""
Composio integration: managed Gmail / Outlook / Teams / Calendar tools.

Composio resolves actions and routes to the user's connected accounts against
its backend using the API key, so this runs wherever the app runs (the key and
network must be present). The SDK is imported lazily so the rest of the app
works even when Composio isn't installed/configured.

Design notes:
- The API key is read from Settings (env / .env) — never hard-coded.
- Action slugs are configurable (defaults in Settings) and can be discovered
  live via `actions(app)`. Results from `execute()` are returned as-is plus a
  best-effort `data` extraction, so the UI can render known fields or raw JSON.
"""
from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.utils.logger import get_logger

logger = get_logger("composio")


class ComposioError(RuntimeError):
    pass


# Per-provider default action slugs, overridable from Settings.
_EMAIL_PROVIDERS = ("gmail", "outlook")
_CAL_PROVIDERS = ("gmail", "outlook")  # gmail -> google calendar


class ComposioService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._toolset = None  # lazily constructed

    # ----- capability / config -----
    @property
    def enabled(self) -> bool:
        return self.settings.composio_enabled

    def _slugs(self) -> dict[str, dict[str, str]]:
        s = self.settings
        return {
            "gmail": {
                "fetch": s.composio_gmail_fetch,
                "send": s.composio_gmail_send,
                "events": s.composio_gcal_events,
            },
            "outlook": {
                "fetch": s.composio_outlook_fetch,
                "send": s.composio_outlook_send,
                "events": s.composio_outlook_events,
            },
        }

    # ----- SDK plumbing -----
    def _ts(self):
        """Return a cached Composio client, or raise a friendly error."""
        if not self.enabled:
            raise ComposioError(
                "Composio is not configured. Set COMPOSIO_API_KEY in backend/.env."
            )
        if self._toolset is None:
            try:
                from composio import Composio  # lazy import
            except Exception as exc:  # noqa: BLE001
                raise ComposioError(
                    "The 'composio' package is not installed. "
                    "Run: pip install composio"
                ) from exc
            try:
                self._toolset = Composio(api_key=self.settings.composio_api_key)
            except Exception as exc:  # noqa: BLE001
                raise ComposioError(f"Could not initialise Composio: {exc}") from exc
        return self._toolset

    # ----- discovery -----
    def connections(self) -> list[dict[str, Any]]:
        """Connected accounts (Gmail/Outlook/Teams/...) with status."""
        ts = self._ts()
        try:
            accounts = ts.connected_accounts.list()
        except Exception as exc:  # noqa: BLE001
            raise ComposioError(f"Failed to list connections: {exc}") from exc
        out: list[dict[str, Any]] = []
        items = getattr(accounts, "items", [])
        for a in items:
            toolkit = getattr(a, "toolkit", None)
            app_name = ""
            if toolkit:
                if isinstance(toolkit, dict):
                    app_name = toolkit.get("slug", "")
                else:
                    app_name = getattr(toolkit, "slug", "")
            out.append(
                {
                    "id": getattr(a, "id", None),
                    "app": app_name.lower(),
                    "status": getattr(a, "status", None),
                    "entity_id": getattr(a, "user_id", None),
                }
            )
        return out

    def actions(self, app: str) -> list[dict[str, Any]]:
        """Discover available action slugs (+ schema) for an app, live."""
        ts = self._ts()
        try:
            # Map app name to toolkit_slug:
            toolkit_slug = app
            if toolkit_slug == "microsoftteams":
                toolkit_slug = "microsoft_teams"
            res = ts.client.tools.list(toolkit_slug=toolkit_slug, timeout=10)
            schemas = getattr(res, "items", [])
        except Exception as exc:  # noqa: BLE001
            raise ComposioError(f"Failed to list actions for {app}: {exc}") from exc
        out: list[dict[str, Any]] = []
        for sch in schemas:
            out.append(
                {
                    "name": getattr(sch, "slug", getattr(sch, "name", None)),
                    "description": (getattr(sch, "description", "") or "")[:160],
                }
            )
        return out

    # ----- generic execution -----
    def execute(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        *,
        connected_account_id: str | None = None,
    ) -> dict[str, Any]:
        ts = self._ts()
        try:
            result = ts.tools.execute(
                slug=action,
                arguments=params or {},
                user_id=self.settings.composio_entity_id,
                connected_account_id=connected_account_id,
                dangerously_skip_version_check=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise ComposioError(f"Action {action} failed: {exc}") from exc
        data = result.get("data", result) if isinstance(result, dict) else result
        return {"action": action, "raw": result, "data": data}

    # ----- convenience: email -----
    def fetch_emails(self, provider: str, limit: int = 10) -> dict[str, Any]:
        provider = provider.lower()
        if provider not in _EMAIL_PROVIDERS:
            raise ComposioError(f"Unknown email provider: {provider}")
        slug = self._slugs()[provider]["fetch"]
        params = {"max_results": limit} if provider == "gmail" else {"top": limit}
        return self.execute(slug, params)

    def send_email(
        self,
        provider: str,
        to: str,
        subject: str,
        body: str,
        attachment: str | None = None,
    ) -> dict[str, Any]:
        provider = provider.lower()
        if provider not in _EMAIL_PROVIDERS:
            raise ComposioError(f"Unknown email provider: {provider}")
        slug = self._slugs()[provider]["send"]
        if provider == "gmail":
            params = {"recipient_email": to, "subject": subject, "body": body}
        else:  # outlook
            params = {"to_email": to, "subject": subject, "body": body}
        if attachment:
            import base64
            import os
            if os.path.exists(attachment):
                try:
                    with open(attachment, "rb") as f:
                        file_data = f.read()
                    encoded = base64.b64encode(file_data).decode("utf-8")
                    # Add base64 variants to accommodate different Composio SDK requirements
                    params["attachment_content"] = encoded
                    params["file_content"] = encoded
                    params["attachment_base64"] = encoded
                    filename = os.path.basename(attachment)
                    params["attachments"] = [
                        {
                            "name": filename,
                            "content": encoded,
                            "mimetype": "application/pdf",
                            "contentType": "application/pdf",
                        }
                    ]
                except Exception as exc:
                    logger.warning("Failed to read/encode attachment %s: %s", attachment, exc)
            else:
                logger.warning("Attachment file %s not found on disk. Passing original path.", attachment)
            
            # Keep original for compatibility/testing
            params["attachment"] = attachment
        return self.execute(slug, params)

    # ----- convenience: calendar -----
    def list_events(self, provider: str, limit: int = 10) -> dict[str, Any]:
        provider = provider.lower()
        if provider not in _CAL_PROVIDERS:
            raise ComposioError(f"Unknown calendar provider: {provider}")
        slug = self._slugs()[provider]["events"]
        if provider == "gmail":
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            # Fetch events starting from 30 days ago to show current/recent events
            start_date = now - timedelta(days=30)
            params = {
                "maxResults": limit,
                "singleEvents": True,
                "orderBy": "startTime",
                "timeMin": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        else:
            params = {"top": limit}
        return self.execute(slug, params)
