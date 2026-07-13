"""Pydantic schemas for the meeting API surface."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MeetingUpload(BaseModel):
    meeting_id: str = Field(..., examples=["M001"])
    title: str = Field(default="Untitled Meeting", examples=["Sprint Meeting"])
    transcript: str = Field(..., examples=["Alice:\nAPI development should finish this week."])
    duration: int | None = Field(default=None, description="Duration in minutes")
    project_id: int | None = Field(default=None, description="Group meetings into a project")


class MeetingUpdate(BaseModel):
    """Edit a meeting. Any field may be omitted to leave it unchanged.

    - title / duration: metadata-only edits (cheap)
    - transcript: replaces the whole transcript and rebuilds memory
    - append_transcript: adds text to the end and rebuilds memory
    """
    title: str | None = None
    duration: int | None = None
    transcript: str | None = None
    append_transcript: str | None = None


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    type: str


class GraphEdgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source: str
    relation: str
    target: str


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    chunk_index: int
    speaker: str | None
    content: str


class ActionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner: str | None
    task: str
    due: str | None
    status: str


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    meeting_id: str
    title: str
    date: datetime
    duration: int | None
    project_id: int | None = None


class ProjectSummary(BaseModel):
    project_id: int
    meetings: int
    titles: list[str] = []


class IngestionResult(BaseModel):
    meeting_id: str
    chunks: int
    entities: int
    edges: int
    action_items: int


class MeetingDetail(MeetingOut):
    raw_transcript: str
    chunks: list[ChunkOut] = []
    entities: list[EntityOut] = []
    edges: list[GraphEdgeOut] = []
    action_items: list[ActionItemOut] = []
