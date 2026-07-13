"""Request/response schemas for the Contact (Composio) section."""
from typing import Any

from pydantic import BaseModel, Field


class CommsStatus(BaseModel):
    enabled: bool
    entity_id: str
    connections: list[dict[str, Any]] = []
    error: str | None = None


class SendEmailRequest(BaseModel):
    provider: str = Field(default="gmail", examples=["gmail", "outlook"])
    to: str = Field(..., examples=["someone@example.com"])
    subject: str = ""
    body: str = ""


class ExecuteRequest(BaseModel):
    action: str = Field(..., examples=["GMAIL_FETCH_EMAILS"])
    params: dict[str, Any] = {}
    connected_account_id: str | None = None


class CommsResult(BaseModel):
    action: str
    data: Any = None
    raw: Any = None
