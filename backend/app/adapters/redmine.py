from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.core.config import settings


class RedmineAdapter:
    def __init__(self, base_url: str, api_key: str, timeout: int | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout or settings.redmine_default_timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers={"X-Redmine-API-Key": self.api_key},
            timeout=self.timeout,
        )

    @retry(stop=stop_after_attempt(settings.redmine_retry_attempts), wait=wait_fixed(settings.redmine_retry_wait_seconds))
    def test_connection(self) -> dict[str, Any]:
        with self._client() as client:
            response = client.get("/projects.json", params={"limit": 1})
            response.raise_for_status()
            data = response.json()
        return {
            "projects": data.get("total_count", 0),
        }

    @retry(
        stop=stop_after_attempt(settings.redmine_retry_attempts),
        wait=wait_fixed(settings.redmine_retry_wait_seconds),
        retry=retry_if_exception_type(httpx.RequestError),
    )
    def fetch_queries(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self._client() as client:
            params: dict[str, Any] = {"limit": 100}
            if project_id:
                # Some Redmine instances only expose queries under the project scope.
                project_response = client.get(f"/projects/{project_id}/queries.json", params=params)
                if project_response.status_code == 404:
                    project_response = client.get("/queries.json", params={"limit": 100, "project_id": project_id})
                project_response.raise_for_status()
                data = project_response.json()
            else:
                response = client.get("/queries.json", params=params)
                if response.status_code == 404:
                    # Fallback when global queries endpoint is disabled.
                    response = client.get("/projects.json", params={"limit": 1})
                    response.raise_for_status()
                    data = {"queries": []}
                else:
                    response.raise_for_status()
                    data = response.json()
        return data.get("queries", []) or []

    @retry(stop=stop_after_attempt(settings.redmine_retry_attempts), wait=wait_fixed(settings.redmine_retry_wait_seconds))
    def _fetch_page(
        self,
        project_id: str | None,
        limit: int,
        offset: int,
        status_id: str | None,
        query_id: str | None,
    ) -> dict[str, Any]:
        with self._client() as client:
            params: dict[str, Any] = {
                "limit": limit,
                "offset": offset,
                "status_id": status_id or "*",
                "include": "custom_fields",
            }
            if project_id:
                params["project_id"] = project_id
            if query_id:
                params["query_id"] = query_id
            response = client.get(
                "/issues.json",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    def fetch_issues(
        self,
        project_id: str | None,
        start_date: date,
        end_date: date,
        status_id: str | None = None,
        query_id: str | None = None,
    ) -> Iterable[dict[str, Any]]:
        limit = 100
        offset = 0
        total = None
        while total is None or offset < total:
            payload = self._fetch_page(project_id, limit, offset, status_id, query_id)
            total = payload.get("total_count", 0)
            issues = payload.get("issues", [])
            for issue in issues:
                created_on = self._parse_datetime(issue.get("created_on"))
                if created_on is None:
                    yield issue
                    continue
                if start_date <= created_on.date() <= end_date:
                    yield issue
            offset += limit

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
