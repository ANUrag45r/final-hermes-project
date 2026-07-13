"""Schemas for the weekly / per-meeting project report."""
from datetime import date, datetime

from pydantic import BaseModel


class MeetingRef(BaseModel):
    meeting_id: str
    title: str
    date: datetime


class Responsibility(BaseModel):
    owner: str
    tasks: list[str]


class Insight(BaseModel):
    """A merit or demerit, with the evidence it was derived from."""
    text: str
    evidence: str | None = None
    source: str | None = None  # speaker and/or meeting id


class ReportStats(BaseModel):
    meetings: int
    people: int
    tasks: int
    graph_edges: int
    open_action_items: int
    done_action_items: int


class ActionItemRef(BaseModel):
    owner: str | None
    task: str
    due: str | None
    status: str
    meeting_id: str


class ProjectReport(BaseModel):
    title: str
    scope_type: str            # "weekly" | "meeting"
    scope_label: str           # human label, e.g. "Week of Jun 15 – Jun 21, 2026"
    generated_at: datetime
    period_start: date | None = None
    period_end: date | None = None
    meetings: list[MeetingRef]
    stats: ReportStats
    responsibilities: list[Responsibility]
    merits: list[Insight]
    demerits: list[Insight]
    action_items: list[ActionItemRef]
    executive_summary: str
    provider: str
