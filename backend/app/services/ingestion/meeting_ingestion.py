"""
Meeting ingestion orchestration.

Owns the end-to-end write flow:
  Stage 2  persist the raw meeting
  Stages 4-7 delegate to GBrain (chunk / entities / graph / vectors)
  derive trackable action items from ownership edges

Depends on AbstractGBrain, so the memory engine is swappable.
"""
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.meeting_schema import IngestionResult, MeetingUpdate, MeetingUpload
from app.services.gbrain.base import AbstractGBrain
from app.utils.logger import get_logger

logger = get_logger("ingestion")


class MeetingIngestionService:
    def __init__(
        self,
        gbrain: AbstractGBrain,
        meeting_repo: MeetingRepository,
        chunk_repo: ChunkRepository,
    ) -> None:
        self.gbrain = gbrain
        self.meeting_repo = meeting_repo
        self.chunk_repo = chunk_repo

    def ingest(self, payload: MeetingUpload) -> IngestionResult:
        existing = self.meeting_repo.get(payload.meeting_id)
        if existing:
            raise ValueError(f"Meeting '{payload.meeting_id}' already exists")

        # Stage 2: raw persistence (no intelligence here).
        self.meeting_repo.create(
            meeting_id=payload.meeting_id,
            title=payload.title,
            transcript=payload.transcript,
            duration=payload.duration,
            project_id=payload.project_id,
        )

        # Stages 4-7: hand to the memory engine.
        result = self.gbrain.ingest(payload.meeting_id, payload.transcript)

        # Derive action items from ownership edges.
        action_items = self._derive_action_items(
            result.get("edge_records", []), result.get("entity_records", [])
        )
        self.chunk_repo.bulk_add_action_items(payload.meeting_id, action_items)

        return IngestionResult(
            meeting_id=payload.meeting_id,
            chunks=result["chunks"],
            entities=result["entities"],
            edges=result["edges"],
            action_items=len(action_items),
        )

    @staticmethod
    def _derive_action_items(edges: list[dict], entities: list[dict]) -> list[dict]:
        dates = [e["name"] for e in entities if e["type"] == "date"]
        due = dates[0] if dates else None
        items: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for edge in edges:
            if edge["relation"] != "responsible_for":
                continue
            key = (edge["source"], edge["target"])
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "owner": edge["source"],
                    "task": edge["target"],
                    "due": due,
                    "status": "open",
                }
            )
        return items

    # ----- edit -----
    def update(self, meeting_id: str, patch: MeetingUpdate) -> IngestionResult:
        meeting = self.meeting_repo.get(meeting_id)
        if not meeting:
            raise LookupError(f"Meeting '{meeting_id}' not found")

        # Work out the new transcript, if it changes.
        new_transcript: str | None = None
        if patch.transcript is not None:
            new_transcript = patch.transcript
        elif patch.append_transcript:
            new_transcript = (
                meeting.raw_transcript.rstrip() + "\n\n" + patch.append_transcript.strip()
            )

        # Apply metadata + transcript changes.
        self.meeting_repo.update_fields(
            meeting,
            title=patch.title,
            transcript=new_transcript,
            duration=patch.duration,
        )

        # If the transcript changed, rebuild this meeting's memory.
        if new_transcript is not None:
            self.gbrain.delete(meeting_id)                 # clear vectors
            self.meeting_repo.clear_derived(meeting_id)    # clear chunks/entities/edges/actions
            result = self.gbrain.ingest(meeting_id, new_transcript)
            action_items = self._derive_action_items(
                result.get("edge_records", []), result.get("entity_records", [])
            )
            self.chunk_repo.bulk_add_action_items(meeting_id, action_items)
            return IngestionResult(
                meeting_id=meeting_id,
                chunks=result["chunks"],
                entities=result["entities"],
                edges=result["edges"],
                action_items=len(action_items),
            )

        # Metadata-only edit: report current counts.
        full = self.meeting_repo.get_with_relations(meeting_id)
        return IngestionResult(
            meeting_id=meeting_id,
            chunks=len(full.chunks) if full else 0,
            entities=len(full.entities) if full else 0,
            edges=len(full.edges) if full else 0,
            action_items=len(full.action_items) if full else 0,
        )

    # ----- delete -----
    def delete(self, meeting_id: str) -> None:
        meeting = self.meeting_repo.get(meeting_id)
        if not meeting:
            raise LookupError(f"Meeting '{meeting_id}' not found")
        self.gbrain.delete(meeting_id)        # clear vectors
        self.meeting_repo.delete(meeting)     # cascade-delete DB rows

        from app.models.processed_file import ProcessedFile
        self.meeting_repo.db.query(ProcessedFile).filter_by(meeting_id=meeting_id).delete()
