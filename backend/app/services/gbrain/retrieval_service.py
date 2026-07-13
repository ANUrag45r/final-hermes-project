"""
Retrieval + context fusion (Stage 8).

Runs graph search and vector search side by side and fuses the results into a
single `RAGContext`. This object is pure evidence — it never contains an answer,
preserving the retrieval/reasoning separation.
"""
from app.repositories.graph_repository import GraphRepository
from app.schemas.chat_schema import GraphFact, RAGContext, VectorHit
from app.services.gbrain.base import AbstractVectorStore
from app.utils.logger import get_logger

logger = get_logger("retrieval")

# Words too generic to be useful graph search terms.
_STOPWORDS = {
    "what", "who", "whom", "whose", "when", "where", "why", "how", "which",
    "task", "tasks", "was", "were", "is", "are", "the", "a", "an", "to", "of",
    "for", "on", "in", "did", "do", "does", "assigned", "about", "and", "with",
}


class RetrievalService:
    def __init__(
        self, graph_repo: GraphRepository, vector_store: AbstractVectorStore
    ) -> None:
        self.graph_repo = graph_repo
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        meeting_id: str | None = None,
        top_k: int = 4,
        meeting_ids: list[str] | None = None,
    ) -> RAGContext:
        graph_facts = self._graph_search(query, meeting_id, meeting_ids)
        vector_hits = self._vector_search(query, meeting_id, top_k, meeting_ids)
        logger.info(
            "Retrieved %d graph facts, %d vector hits for query=%r",
            len(graph_facts), len(vector_hits), query,
        )
        return RAGContext(
            query=query, graph_facts=graph_facts, vector_hits=vector_hits
        )

    def _graph_search(
        self, query: str, meeting_id: str | None, meeting_ids: list[str] | None
    ) -> list[GraphFact]:
        terms = [t for t in _split_terms(query) if t not in _STOPWORDS]
        found: dict[int, GraphFact] = {}
        for term in terms:
            for edge in self.graph_repo.search(
                term, meeting_id=meeting_id, meeting_ids=meeting_ids
            ):
                found[edge.id] = GraphFact(
                    source=edge.source,
                    relation=edge.relation,
                    target=edge.target,
                    meeting_id=edge.meeting_id,
                )
        return list(found.values())

    def _vector_search(
        self,
        query: str,
        meeting_id: str | None,
        top_k: int,
        meeting_ids: list[str] | None,
    ) -> list[VectorHit]:
        hits = self.vector_store.search(
            query, meeting_id=meeting_id, top_k=top_k, meeting_ids=meeting_ids
        )
        return [VectorHit(**hit) for hit in hits]


def _split_terms(query: str) -> list[str]:
    import re

    return [w for w in re.findall(r"[A-Za-z0-9]+", query.lower()) if len(w) > 1]
