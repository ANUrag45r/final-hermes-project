"""
Entity extraction (Stage 5).

This is a dependency-free heuristic implementation so the system runs offline.
It recognises three entity types — person, task, date — using speaker labels,
a small task vocabulary, capitalised noun phrases, and date patterns.

In production this class is replaced by the installed GBrain's NER; nothing
else changes because callers depend on `AbstractEntityExtractor`.
"""
import re

# Recurring task keywords seen in engineering / governance meetings.
_TASK_KEYWORDS = {
    "api", "authentication", "auth", "testing", "test", "deployment", "deploy",
    "development", "design", "review", "documentation", "docs", "migration",
    "integration", "release", "bug", "feature", "database", "backend",
    "frontend", "security", "audit", "onboarding", "rollout", "qa",
}

_DATE_PATTERNS = [
    r"\btoday\b", r"\btomorrow\b", r"\byesterday\b", r"\bthis week\b",
    r"\bnext week\b", r"\bthis month\b", r"\bend of (?:the )?(?:week|month|sprint)\b",
    r"\bmonday\b", r"\btuesday\b", r"\bwednesday\b", r"\bthursday\b",
    r"\bfriday\b", r"\bsaturday\b", r"\bsunday\b",
    r"\bq[1-4]\b", r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b",
]
_DATE_RE = re.compile("|".join(_DATE_PATTERNS), re.IGNORECASE)

# Capitalised multi-word noun phrases, e.g. "Authentication Module".
_NOUN_PHRASE_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")


def _titleize(token: str) -> str:
    return " ".join(w.capitalize() for w in token.split())


class EntityExtractor:
    def extract(self, chunks: list[dict]) -> list[dict]:
        people: set[str] = set()
        tasks: set[str] = set()
        dates: set[str] = set()

        for chunk in chunks:
            if chunk.get("speaker"):
                people.add(chunk["speaker"].strip())

            content = chunk.get("content", "")
            lowered = content.lower()

            # Tasks: keyword hits, normalised to a readable label.
            for word in re.findall(r"[a-zA-Z]+", lowered):
                if word in _TASK_KEYWORDS:
                    tasks.add(self._normalize_task(word))

            # Tasks: capitalised noun phrases that look like deliverables.
            for phrase in _NOUN_PHRASE_RE.findall(content):
                if phrase.strip() in people:
                    continue
                low = phrase.lower()
                if any(k in low for k in _TASK_KEYWORDS):
                    tasks.add(_titleize(phrase))

            # Dates.
            for match in _DATE_RE.findall(content):
                hit = match if isinstance(match, str) else next(filter(None, match), "")
                if hit:
                    dates.add(_titleize(hit.strip()))

        entities: list[dict] = []
        entities += [{"name": p, "type": "person"} for p in sorted(people)]
        entities += [{"name": t, "type": "task"} for t in sorted(tasks)]
        entities += [{"name": d, "type": "date"} for d in sorted(dates)]
        return entities

    @staticmethod
    def _normalize_task(word: str) -> str:
        mapping = {
            "api": "API Development",
            "auth": "Authentication",
            "authentication": "Authentication",
            "test": "Testing",
            "testing": "Testing",
            "deploy": "Deployment",
            "deployment": "Deployment",
            "docs": "Documentation",
            "documentation": "Documentation",
            "qa": "QA",
            "development": "Development",
        }
        return mapping.get(word, word.capitalize())
