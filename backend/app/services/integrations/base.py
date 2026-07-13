"""
Interfaces for external messaging integrations (Outlook mail, Teams).

Business logic depends on `AbstractMailClient`, never on Microsoft Graph
directly — so the provider can be swapped or mocked. A `NotConfiguredError`
signals that credentials are missing, which the chat layer turns into a helpful
message instead of a crash.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class NotConfiguredError(RuntimeError):
    """Raised when an integration is used but its credentials are absent."""


class EmailSummary(BaseModel):
    id: str
    sender: str
    subject: str
    received: str
    preview: str


@runtime_checkable
class AbstractMailClient(Protocol):
    def list_recent(self, count: int) -> list[EmailSummary]: ...
    def send(self, to: str, subject: str, body: str) -> None: ...


@runtime_checkable
class AbstractTeamsClient(Protocol):
    def send_chat_message(self, chat_id: str, text: str) -> None: ...
