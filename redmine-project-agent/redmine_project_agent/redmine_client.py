from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Issue, ProjectSnapshot, Version


@dataclass(frozen=True)
class RedmineClient:
    base_url: str
    api_key: str
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "RedmineClient":
        base_url = os.environ.get("REDMINE_URL", "").rstrip("/")
        api_key = os.environ.get("REDMINE_API_KEY", "")
        if not base_url or not api_key:
            raise RuntimeError("Defina REDMINE_URL e REDMINE_API_KEY.")
        return cls(base_url=base_url, api_key=api_key)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = f"?{urlencode(params or {})}" if params else ""
        request = Request(
            f"{self.base_url}{path}{query}",
            headers={
                "X-Redmine-API-Key": self.api_key,
                "Accept": "application/json",
            },
            method="GET",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_project_snapshot(self, project_id: int | str) -> ProjectSnapshot:
        project_payload = self._get(f"/projects/{project_id}.json")
        issues = self._fetch_all_issues(project_id)
        versions = self._fetch_versions(project_id)
        project = project_payload.get("project", {})
        return ProjectSnapshot(
            project_id=project.get("id", project_id),
            project_name=str(project.get("name", project_id)),
            issues=issues,
            versions=versions,
        )

    def _fetch_all_issues(self, project_id: int | str) -> list[Issue]:
        limit = 100
        offset = 0
        issues: list[Issue] = []
        while True:
            payload = self._get(
                "/issues.json",
                {
                    "project_id": project_id,
                    "status_id": "*",
                    "limit": limit,
                    "offset": offset,
                    "include": "journals",
                },
            )
            batch = payload.get("issues", [])
            issues.extend(Issue.from_redmine(item) for item in batch)
            total = int(payload.get("total_count", len(issues)))
            offset += limit
            if offset >= total or not batch:
                return issues

    def _fetch_versions(self, project_id: int | str) -> list[Version]:
        payload = self._get(f"/projects/{project_id}/versions.json")
        return [Version.from_redmine(item) for item in payload.get("versions", [])]
