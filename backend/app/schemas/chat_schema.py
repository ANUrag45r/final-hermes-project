"""Schemas for the chat / retrieval surface.

RAGContext is the contract between the retrieval layer (GBrain) and the
reasoning layer (Hermes). It deliberately carries *evidence*, never an answer.
"""
from pydantic import BaseModel, Field


class GraphFact(BaseModel):
    source: str
    relation: str
    target: str
    meeting_id: str | None = None

    def as_text(self) -> str:
        return f"{self.source} {self.relation} {self.target}"


class VectorHit(BaseModel):
    content: str
    speaker: str | None = None
    meeting_id: str | None = None
    score: float = 0.0


class RAGContext(BaseModel):
    """Fused graph + vector evidence handed to Hermes. Contains no answer."""
    query: str
    graph_facts: list[GraphFact] = Field(default_factory=list)
    vector_hits: list[VectorHit] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.graph_facts and not self.vector_hits


class ChatRequest(BaseModel):
    query: str = Field(..., examples=["What task was assigned to Bob?"])
    meeting_id: str | None = Field(
        default=None, description="Optional: restrict retrieval to one meeting"
    )
    project_id: int | None = Field(
        default=None, description="Optional: restrict retrieval to one project"
    )
    top_k: int = Field(default=4, ge=1, le=20)


class ChatResponse(BaseModel):
    answer: str
    context: RAGContext
    provider: str
    action: str = "rag"  # "rag" | "mail_fetch" | "mail_send" | "mail_help"
    emails: list[dict] | None = None
