"""
Report builder.

Aggregates everything GBrain knows about a scope (one meeting, or every meeting
in a week) and derives a grounded merits / demerits assessment of the project.

Nothing here is invented — every merit and demerit is backed by a concrete
signal: an ownership edge, an action-item status, or a progress / blocker cue
found in the transcript itself. This means the report is meaningful even with
the offline `local` reasoner.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from app.repositories.report_repository import ReportRepository
from app.schemas.report_schema import (
    ActionItemRef,
    Insight,
    MeetingRef,
    ProjectReport,
    ReportStats,
    Responsibility,
)

# Progress signals (merits) and risk signals (demerits) scanned in transcripts.
_MERIT_CUES = {
    "complete", "completed", "done", "finished", "shipped", "ready",
    "resolved", "passed", "deployed", "merged", "approved", "on track",
    "delivered", "launched",
}
_DEMERIT_CUES = {
    "pending", "blocked", "blocker", "delayed", "stuck", "risk", "fail",
    "failing", "broken", "behind", "waiting", "overdue", "incomplete",
    "issue", "concern", "missed", "slipping",
}

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _excerpt(content: str, cue: str) -> str:
    """Return the sentence containing the cue, trimmed for the report."""
    for sentence in _SENT_SPLIT.split(content):
        if cue in sentence.lower():
            s = sentence.strip()
            return s if len(s) <= 160 else s[:157] + "…"
    return content[:157] + ("…" if len(content) > 157 else "")


class ReportBuilder:
    def __init__(self, repo: ReportRepository) -> None:
        self.repo = repo

    # --- public scopes --------------------------------------------------
    def for_meeting(self, meeting_id: str) -> ProjectReport | None:
        meeting = self.repo.meeting(meeting_id)
        if not meeting:
            return None
        label = f"Meeting {meeting.meeting_id} — {meeting.title}"
        return self._assemble(
            scope_type="meeting",
            scope_label=label,
            meetings=[meeting],
            period_start=meeting.date.date(),
            period_end=meeting.date.date(),
        )

    def for_week(self, any_day: date) -> ProjectReport:
        start = any_day - timedelta(days=any_day.weekday())  # Monday
        end = start + timedelta(days=6)  # Sunday
        start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
        end_dt = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=timezone.utc)
        meetings = self.repo.meetings_in_range(start_dt, end_dt)
        label = (
            f"Week of {start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}"
        )
        return self._assemble(
            scope_type="weekly",
            scope_label=label,
            meetings=meetings,
            period_start=start,
            period_end=end,
        )

    def for_project(self, project_id: int) -> ProjectReport:
        meetings = self.repo.meetings_for_project(project_id)
        return self._assemble(
            scope_type="project",
            scope_label=f"Project {project_id}",
            meetings=meetings,
            period_start=None,
            period_end=None,
        )

    def for_all(self) -> ProjectReport:
        meetings = self.repo.all_meetings()
        return self._assemble(
            scope_type="all",
            scope_label="All meetings",
            meetings=meetings,
            period_start=None,
            period_end=None,
        )

    # --- core assembly --------------------------------------------------
    def _assemble(
        self,
        scope_type: str,
        scope_label: str,
        meetings: list,
        period_start: date | None,
        period_end: date | None,
    ) -> ProjectReport:
        ids = [m.meeting_id for m in meetings]
        chunks = self.repo.chunks_for(ids)
        entities = self.repo.entities_for(ids)
        edges = self.repo.edges_for(ids)
        actions = self.repo.action_items_for(ids)

        people = sorted({e.name for e in entities if e.type == "person"})
        tasks = sorted({e.name for e in entities if e.type == "task"})

        responsibilities = self._responsibilities(edges)
        merits = self._merits(chunks, edges, actions, responsibilities)
        demerits = self._demerits(chunks, edges, actions, tasks)

        stats = ReportStats(
            meetings=len(meetings),
            people=len(people),
            tasks=len(tasks),
            graph_edges=len(edges),
            open_action_items=sum(1 for a in actions if a.status == "open"),
            done_action_items=sum(1 for a in actions if a.status == "done"),
        )

        return ProjectReport(
            title="Project Governance Brain — Status Report",
            scope_type=scope_type,
            scope_label=scope_label,
            generated_at=_utcnow(),
            period_start=period_start,
            period_end=period_end,
            meetings=[
                MeetingRef(meeting_id=m.meeting_id, title=m.title, date=m.date)
                for m in meetings
            ],
            stats=stats,
            responsibilities=responsibilities,
            merits=merits,
            demerits=demerits,
            action_items=[
                ActionItemRef(
                    owner=a.owner,
                    task=a.task,
                    due=a.due,
                    status=a.status,
                    meeting_id=a.meeting_id,
                )
                for a in actions
            ],
            executive_summary=self._summary(stats, merits, demerits, scope_label),
            provider="builder",  # overridden by ReportService if an LLM enriches it
        )

    # --- derivations ----------------------------------------------------
    @staticmethod
    def _responsibilities(edges) -> list[Responsibility]:
        owned: dict[str, set[str]] = {}
        for e in edges:
            if e.relation == "responsible_for":
                owned.setdefault(e.source, set()).add(e.target)
        return [
            Responsibility(owner=owner, tasks=sorted(tasks))
            for owner, tasks in sorted(owned.items())
        ]

    @staticmethod
    def _merits(chunks, edges, actions, responsibilities) -> list[Insight]:
        merits: list[Insight] = []

        if responsibilities:
            owned = sum(len(r.tasks) for r in responsibilities)
            merits.append(
                Insight(
                    text=(
                        f"{owned} task(s) have a clear owner across "
                        f"{len(responsibilities)} contributor(s) — accountability "
                        "is well defined."
                    )
                )
            )

        for a in actions:
            if a.status == "done":
                merits.append(
                    Insight(
                        text=f"Completed: {a.task}"
                        + (f" (owner: {a.owner})" if a.owner else ""),
                        source=a.meeting_id,
                    )
                )

        seen: set[str] = set()
        for c in chunks:
            low = c.content.lower()
            for cue in _MERIT_CUES:
                if cue in low:
                    ex = _excerpt(c.content, cue)
                    if ex in seen:
                        continue
                    seen.add(ex)
                    merits.append(
                        Insight(text="Progress signalled", evidence=ex, source=c.speaker)
                    )
                    break

        if not merits:
            merits.append(
                Insight(text="No explicit progress signals recorded this period.")
            )
        return merits

    @staticmethod
    def _demerits(chunks, edges, actions, tasks) -> list[Insight]:
        demerits: list[Insight] = []

        # Open action items with no deadline are a planning gap.
        for a in actions:
            if a.status == "open" and not a.due:
                demerits.append(
                    Insight(
                        text=f"Open item without a deadline: {a.task}"
                        + (f" (owner: {a.owner})" if a.owner else " (unassigned)"),
                        source=a.meeting_id,
                    )
                )

        # Tasks discussed but never owned.
        owned = {e.target for e in edges if e.relation == "responsible_for"}
        discussed = {e.target for e in edges if e.relation == "discusses"}
        for t in sorted(discussed - owned):
            demerits.append(
                Insight(text=f"Discussed but unassigned: {t}")
            )

        # Blocker / risk cues from the transcript.
        seen: set[str] = set()
        for c in chunks:
            low = c.content.lower()
            for cue in _DEMERIT_CUES:
                if cue in low:
                    ex = _excerpt(c.content, cue)
                    if ex in seen:
                        continue
                    seen.add(ex)
                    demerits.append(
                        Insight(text=f"Risk: {cue}", evidence=ex, source=c.speaker)
                    )
                    break

        if not demerits:
            demerits.append(
                Insight(text="No blockers or risks surfaced this period.")
            )
        return demerits

    @staticmethod
    def _summary(stats, merits, demerits, scope_label) -> str:
        return (
            f"{scope_label}. Across {stats.meetings} meeting(s), the project "
            f"engaged {stats.people} contributor(s) on {stats.tasks} distinct "
            f"task(s), captured in {stats.graph_edges} relationship(s). "
            f"{stats.done_action_items} action item(s) are complete and "
            f"{stats.open_action_items} remain open. "
            f"{len(merits)} positive signal(s) and {len(demerits)} risk(s) were "
            "identified — see the sections below."
        )
