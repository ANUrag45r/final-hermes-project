"""ORM models package. Importing it registers every table on the metadata."""
from app.models.action_item import ActionItem
from app.models.auto_ingest_settings import AutoIngestSettings
from app.models.auto_send_settings import AutoSendSettings
from app.models.entity import Entity
from app.models.graph_edge import GraphEdge
from app.models.meeting import Meeting
from app.models.processed_file import ProcessedFile
from app.models.transcript_chunk import TranscriptChunk

__all__ = [
    "Meeting",
    "TranscriptChunk",
    "Entity",
    "GraphEdge",
    "ActionItem",
    "AutoSendSettings",
    "AutoIngestSettings",
    "ProcessedFile",
]
