"""
Relationship extraction (Stage 6).

Builds (source)-[relation]->(target) edges linking people to tasks. Ownership
cues ("I'll", "I will", "I am", "assigned to", "responsible for", "pending")
upgrade a `discusses` edge to `responsible_for`.

Local heuristic; replaced by GBrain's relation extractor in production.
"""
import re

_OWNERSHIP_CUES = (
    "i'll", "i will", "i am", "i'm", "my ", "assigned", "responsible",
    "owner", "i own", "owns", "owned", "own the", "pending", "i can",
    "i should", "i need to", "let me",
)


class GraphExtractor:
    def extract(self, chunks: list[dict], entities: list[dict]) -> list[dict]:
        tasks = [e["name"] for e in entities if e["type"] == "task"]
        edges: list[dict] = []
        seen: set[tuple[str, str, str]] = set()

        def add(source: str, relation: str, target: str) -> None:
            key = (source.lower(), relation, target.lower())
            if source and target and key not in seen:
                seen.add(key)
                edges.append({"source": source, "relation": relation, "target": target})

        for chunk in chunks:
            speaker = (chunk.get("speaker") or "").strip()
            if not speaker:
                continue
            content = chunk.get("content", "")
            lowered = content.lower()
            owns = any(cue in lowered for cue in _OWNERSHIP_CUES)

            for task in tasks:
                if self._mentions(lowered, task):
                    add(speaker, "responsible_for" if owns else "discusses", task)

        return edges

    @staticmethod
    def _mentions(lowered_content: str, task: str) -> bool:
        # Match the task or any of its significant words.
        words = [w for w in re.findall(r"[a-z]+", task.lower()) if len(w) > 2]
        return any(w in lowered_content for w in words)
