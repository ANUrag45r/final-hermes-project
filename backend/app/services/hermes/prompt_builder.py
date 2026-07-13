"""
Prompt construction for Hermes.

Turns a question + RAGContext into a grounded prompt that instructs the model
to answer only from the supplied evidence. Kept separate from the client so the
prompting strategy can evolve without touching transport code.
"""
from app.schemas.chat_schema import RAGContext

SYSTEM_PROMPT = (
    "You are Project Governance Brain, an organizational memory assistant. "
    "Answer the question using ONLY the meeting evidence provided. "
    "Cite people and tasks exactly as named. If the evidence does not contain "
    "the answer, say you don't have that information. Be concise."
)


class PromptBuilder:
    def build(self, question: str, context: RAGContext) -> str:
        graph_block = "\n".join(
            f"- {f.source} {f.relation} {f.target}" for f in context.graph_facts
        ) or "- (none)"

        vector_block = "\n".join(
            f"- {('[' + h.speaker + '] ') if h.speaker else ''}{h.content}"
            for h in context.vector_hits
        ) or "- (none)"

        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"=== Knowledge Graph Facts ===\n{graph_block}\n\n"
            f"=== Relevant Transcript Excerpts ===\n{vector_block}\n\n"
            f"=== Question ===\n{question}\n\n"
            f"=== Answer ==="
        )
