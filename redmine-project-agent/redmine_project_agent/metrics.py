from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone

from .models import Issue, ProjectSnapshot


HIGH_PRIORITY_KEYWORDS = ("alta", "high", "urgent", "urgente", "imediata", "immediate", "crítica", "critical")


@dataclass(frozen=True)
class ProjectMetrics:
    total_issues: int
    open_issues: int
    closed_issues: int
    overdue_issues: list[Issue]
    unassigned_issues: list[Issue]
    stale_issues: list[Issue]
    high_priority_open_issues: list[Issue]
    due_soon_versions: list[str]
    in_progress_count: int
    by_assignee: dict[str, int]

    @property
    def completion_rate(self) -> float:
        if self.total_issues == 0:
            return 1.0
        return self.closed_issues / self.total_issues


def calculate_metrics(snapshot: ProjectSnapshot, days_stale: int = 7, today: date | None = None) -> ProjectMetrics:
    today = today or date.today()
    now = datetime.now(timezone.utc)
    open_issues = [issue for issue in snapshot.issues if not issue.is_closed]
    closed_issues = [issue for issue in snapshot.issues if issue.is_closed]

    overdue = [
        issue for issue in open_issues
        if issue.due_date is not None and issue.due_date < today
    ]
    unassigned = [issue for issue in open_issues if not issue.assigned_to]
    stale = [
        issue for issue in open_issues
        if issue.updated_on is not None and (now - issue.updated_on.astimezone(timezone.utc)).days >= days_stale
    ]
    high_priority = [
        issue for issue in open_issues
        if any(keyword in issue.priority.lower() for keyword in HIGH_PRIORITY_KEYWORDS)
    ]
    in_progress = [
        issue for issue in open_issues
        if any(token in issue.status.lower() for token in ("andamento", "progress", "doing", "desenvolvimento"))
    ]
    due_soon_versions = [
        version.name for version in snapshot.versions
        if version.due_date is not None and 0 <= (version.due_date - today).days <= 14
    ]
    by_assignee = Counter(issue.assigned_to or "Sem responsável" for issue in open_issues)

    return ProjectMetrics(
        total_issues=len(snapshot.issues),
        open_issues=len(open_issues),
        closed_issues=len(closed_issues),
        overdue_issues=overdue,
        unassigned_issues=unassigned,
        stale_issues=stale,
        high_priority_open_issues=high_priority,
        due_soon_versions=due_soon_versions,
        in_progress_count=len(in_progress),
        by_assignee=dict(by_assignee.most_common()),
    )
