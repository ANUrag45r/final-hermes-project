"""
GBrainService — the single memory engine (implements AbstractGBrain).

Coordinates the ingestion pipeline (chunk -> entities -> graph -> vectors ->
persistence) and the retrieval pipeline (graph + vector fusion). It is the only
component allowed to touch the memory stores, and it NEVER generates answers.
"""
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.graph_repository import GraphRepository
from app.schemas.chat_schema import RAGContext
from app.services.gbrain.base import (
    AbstractChunker,
    AbstractEntityExtractor,
    AbstractGraphExtractor,
    AbstractVectorStore,
)
from app.services.gbrain.retrieval_service import RetrievalService
from app.utils.logger import get_logger

logger = get_logger("gbrain")


class GBrainService:
    def __init__(
        self,
        chunker: AbstractChunker,
        entity_extractor: AbstractEntityExtractor,
        graph_extractor: AbstractGraphExtractor,
        vector_store: AbstractVectorStore,
        chunk_repo: ChunkRepository,
        graph_repo: GraphRepository,
    ) -> None:
        self.chunker = chunker
        self.entity_extractor = entity_extractor
        self.graph_extractor = graph_extractor
        self.vector_store = vector_store
        self.chunk_repo = chunk_repo
        self.graph_repo = graph_repo
        self.retrieval = RetrievalService(graph_repo, vector_store)

    # ----- write path (Stages 4-7) -----
    def ingest(self, meeting_id: str, transcript: str) -> dict:
        logger.info("Ingesting meeting %s", meeting_id)

        chunks = self.chunker.chunk(transcript)              # Stage 4
        entities = self.entity_extractor.extract(chunks)     # Stage 5
        edges = self.graph_extractor.extract(chunks, entities)  # Stage 6

        # Persist structured memory.
        self.chunk_repo.bulk_add_chunks(meeting_id, chunks)
        self.chunk_repo.bulk_add_entities(meeting_id, entities)
        self.graph_repo.bulk_add_edges(meeting_id, edges)

        # Persist vector memory (Stage 7).
        self.vector_store.upsert(meeting_id, chunks)

        result = {
            "meeting_id": meeting_id,
            "chunks": len(chunks),
            "entities": len(entities),
            "edges": len(edges),
            "entity_records": entities,
            "edge_records": edges,
        }
        logger.info(
            "Ingested %s: %d chunks, %d entities, %d edges",
            meeting_id, result["chunks"], result["entities"], result["edges"],
        )
        return result

    # ----- read path (Stage 8) -----
    def search(
        self,
        query: str,
        meeting_id: str | None = None,
        top_k: int = 4,
        meeting_ids: list[str] | None = None,
    ) -> RAGContext:
        return self.retrieval.retrieve(
            query, meeting_id=meeting_id, top_k=top_k, meeting_ids=meeting_ids
        )

    # ----- delete path -----
    def delete(self, meeting_id: str) -> None:
        """Forget a meeting: clear its vectors (DB rows cascade via the repo)."""
        self.vector_store.delete(meeting_id)
        logger.info("Cleared memory vectors for meeting %s", meeting_id)
