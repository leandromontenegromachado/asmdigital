from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


@dataclass(frozen=True)
class NamedRef:
    id: int | None
    name: str

    @classmethod
    def from_redmine(cls, data: dict[str, Any] | None) -> "NamedRef | None":
        if not data:
            return None
        return cls(id=data.get("id"), name=str(data.get("name", "")))


@dataclass(frozen=True)
class Issue:
    id: int
    subject: str
    status: str
    priority: str
    tracker: str | None = None
    assigned_to: str | None = None
    author: str | None = None
    due_date: date | None = None
    updated_on: datetime | None = None
    created_on: datetime | None = None
    done_ratio: int | None = None
    fixed_version: str | None = None
    is_closed: bool = False

    @classmethod
    def from_redmine(cls, data: dict[str, Any]) -> "Issue":
        assigned = NamedRef.from_redmine(data.get("assigned_to"))
        author = NamedRef.from_redmine(data.get("author"))
        priority = NamedRef.from_redmine(data.get("priority"))
        status = NamedRef.from_redmine(data.get("status"))
        tracker = NamedRef.from_redmine(data.get("tracker"))
        fixed_version = NamedRef.from_redmine(data.get("fixed_version"))
        return cls(
            id=int(data["id"]),
            subject=str(data.get("subject", "")),
            status=status.name if status else "",
            priority=priority.name if priority else "",
            tracker=tracker.name if tracker else None,
            assigned_to=assigned.name if assigned else None,
            author=author.name if author else None,
            due_date=parse_date(data.get("due_date")),
            updated_on=parse_datetime(data.get("updated_on")),
            created_on=parse_datetime(data.get("created_on")),
            done_ratio=data.get("done_ratio"),
            fixed_version=fixed_version.name if fixed_version else None,
            is_closed=bool(data.get("status", {}).get("is_closed", False)),
        )


@dataclass(frozen=True)
class Version:
    id: int
    name: str
    due_date: date | None = None
    status: str | None = None

    @classmethod
    def from_redmine(cls, data: dict[str, Any]) -> "Version":
        return cls(
            id=int(data["id"]),
            name=str(data.get("name", "")),
            due_date=parse_date(data.get("due_date")),
            status=data.get("status"),
        )


@dataclass(frozen=True)
class ProjectSnapshot:
    project_id: int | str
    project_name: str
    issues: list[Issue] = field(default_factory=list)
    versions: list[Version] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ProjectSnapshot":
        issues = [issue_from_json(item) for item in data.get("issues", [])]
        versions = [version_from_json(item) for item in data.get("versions", [])]
        return cls(
            project_id=data.get("project_id", data.get("id", "unknown")),
            project_name=str(data.get("project_name", data.get("name", "Projeto"))),
            issues=issues,
            versions=versions,
        )


def issue_from_json(item: dict[str, Any]) -> Issue:
    if isinstance(item.get("status"), dict):
        return Issue.from_redmine(item)
    return Issue(
        id=int(item["id"]),
        subject=str(item.get("subject", "")),
        status=str(item.get("status", "")),
        priority=str(item.get("priority", "")),
        tracker=item.get("tracker"),
        assigned_to=item.get("assigned_to"),
        author=item.get("author"),
        due_date=parse_date(item.get("due_date")) if not isinstance(item.get("due_date"), date) else item.get("due_date"),
        updated_on=parse_datetime(item.get("updated_on")) if not isinstance(item.get("updated_on"), datetime) else item.get("updated_on"),
        created_on=parse_datetime(item.get("created_on")) if not isinstance(item.get("created_on"), datetime) else item.get("created_on"),
        done_ratio=item.get("done_ratio"),
        fixed_version=item.get("fixed_version"),
        is_closed=bool(item.get("is_closed", False)),
    )


def version_from_json(item: dict[str, Any]) -> Version:
    if isinstance(item.get("id"), int) and isinstance(item.get("due_date"), str):
        return Version(
            id=int(item["id"]),
            name=str(item.get("name", "")),
            due_date=parse_date(item.get("due_date")),
            status=item.get("status"),
        )
    if isinstance(item.get("due_date"), date):
        return Version(**item)
    return Version.from_redmine(item)
