from __future__ import annotations

import html
import re
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

    @retry(stop=stop_after_attempt(settings.redmine_retry_attempts), wait=wait_fixed(settings.redmine_retry_wait_seconds), reraise=True)
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
        reraise=True,
    )
    def fetch_queries(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self._client() as client:
            params: dict[str, Any] = {"limit": 100}
            responses: list[httpx.Response] = []
            if project_id:
                # Redmine versions differ here: some support only the global endpoint
                # with project_id, some support the project-scoped endpoint, and some
                # disable the JSON queries endpoint while still rendering saved queries
                # on the issues page.
                for path, request_params in (
                    ("/queries.json", {"limit": 100, "project_id": project_id}),
                    (f"/projects/{project_id}/queries.json", params),
                    ("/queries.json", params),
                ):
                    response = client.get(path, params=request_params)
                    responses.append(response)
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    data = self._json_or_empty(response)
                    queries = data.get("queries", []) or []
                    if queries:
                        return queries
                html_queries = self._fetch_queries_from_issues_html(client, project_id)
                if html_queries:
                    return html_queries
                if responses:
                    responses[-1].raise_for_status()
                return []
            else:
                response = client.get("/queries.json", params=params)
                if response.status_code == 404:
                    # Fallback when global queries endpoint is disabled.
                    response = client.get("/projects.json", params={"limit": 1})
                    response.raise_for_status()
                    data = {"queries": []}
                else:
                    response.raise_for_status()
                    data = self._json_or_empty(response)
        return data.get("queries", []) or []

    @staticmethod
    def _json_or_empty(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {"queries": []}
        return data if isinstance(data, dict) else {"queries": []}

    def _fetch_queries_from_issues_html(self, client: httpx.Client, project_id: str) -> list[dict[str, Any]]:
        response = client.get(
            f"/projects/{project_id}/issues",
            params={"set_filter": 1},
            headers={"Accept": "text/html"},
        )
        if response.status_code == 404:
            response = client.get("/issues", params={"set_filter": 1, "project_id": project_id}, headers={"Accept": "text/html"})
        if response.status_code == 404:
            return []
        response.raise_for_status()
        body = response.text
        queries: dict[int, dict[str, Any]] = {}
        for match in re.finditer(r'href="[^"]*?[?&]query_id=(?P<id>\d+)[^"]*"[^>]*>(?P<name>.*?)</a>', body, flags=re.I | re.S):
            query_id = int(match.group("id"))
            name = re.sub(r"<[^>]+>", "", match.group("name"))
            queries[query_id] = {
                "id": query_id,
                "name": html.unescape(name).strip() or f"Query {query_id}",
                "is_public": None,
            }
        return list(queries.values())

    def fetch_query_columns(self, project_id: str | None, query_id: str) -> list[dict[str, str]]:
        with self._client() as client:
            paths: list[tuple[str, dict[str, Any]]] = []
            if project_id:
                paths.append((f"/projects/{project_id}/issues", {"query_id": query_id}))
            paths.append(("/issues", {"query_id": query_id, **({"project_id": project_id} if project_id else {})}))

            for path, params in paths:
                response = client.get(path, params=params, headers={"Accept": "text/html"})
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                columns = self._extract_columns_from_issues_html(response.text)
                if columns:
                    return columns
        return []

    @staticmethod
    def _extract_columns_from_issues_html(body: str) -> list[dict[str, str]]:
        header_match = re.search(r"<thead[^>]*>(?P<thead>.*?)</thead>", body, flags=re.I | re.S)
        if not header_match:
            return []
        columns: list[dict[str, str]] = []
        for match in re.finditer(r"<th(?P<attrs>[^>]*)>(?P<label>.*?)</th>", header_match.group("thead"), flags=re.I | re.S):
            attrs = match.group("attrs") or ""
            label = re.sub(r"<[^>]+>", "", match.group("label"))
            label = html.unescape(label).strip()
            if not label or label.lower() in {"#", "checkbox"}:
                continue
            class_match = re.search(r'class="(?P<class>[^"]+)"', attrs, flags=re.I)
            class_names = class_match.group("class").split() if class_match else []
            key = next((name for name in class_names if name not in {"checkbox", "buttons", "hide-when-print"}), "")
            columns.append({"key": key or label, "label": label})
        return columns

    @retry(stop=stop_after_attempt(settings.redmine_retry_attempts), wait=wait_fixed(settings.redmine_retry_wait_seconds), reraise=True)
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
        apply_date_filter: bool = True,
    ) -> Iterable[dict[str, Any]]:
        limit = 100
        offset = 0
        total = None
        while total is None or offset < total:
            payload = self._fetch_page(project_id, limit, offset, status_id, query_id)
            total = payload.get("total_count", 0)
            issues = payload.get("issues", [])
            for issue in issues:
                if not apply_date_filter:
                    yield issue
                    continue
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
