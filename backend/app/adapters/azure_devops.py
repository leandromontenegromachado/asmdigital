from __future__ import annotations

from collections.abc import Iterable
from typing import Any
import base64
import re

import httpx

PBI_TYPES = {"Product Backlog Item", "User Story"}
TASK_TYPES = {"Task"}
DONE_STATES = {"done", "closed", "resolved", "removed"}


class AzureDevOpsAdapter:
    def __init__(
        self,
        organization_url: str,
        personal_access_token: str,
        *,
        api_version: str = "7.1",
        timeout: int = 30,
    ) -> None:
        if not organization_url:
            raise ValueError("organization_url is required")
        if not personal_access_token:
            raise ValueError("personal_access_token is required")

        self.organization_url = organization_url.rstrip("/")
        self.api_version = api_version
        self.timeout = timeout

        token = base64.b64encode(f":{personal_access_token}".encode("utf-8")).decode("ascii")
        self._headers = {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def test_connection(self) -> dict[str, Any]:
        url = f"{self.organization_url}/_apis/projects"
        response = httpx.get(
            url,
            headers=self._headers,
            params={"$top": 1, "api-version": self.api_version},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        projects = payload.get("value", []) if isinstance(payload, dict) else []
        return {
            "ok": True,
            "projects_count": int(payload.get("count", len(projects))) if isinstance(payload, dict) else len(projects),
            "sample_project": projects[0].get("name") if projects else None,
        }

    def query_board_snapshot(
        self,
        *,
        project: str,
        team: str | None = None,
        area_path: str | None = None,
        iteration_path: str | None = None,
        top: int = 200,
    ) -> dict[str, Any]:
        if not project:
            raise ValueError("project is required")

        wiql = self._build_wiql(project, area_path=area_path, iteration_path=iteration_path)
        ids = self._run_wiql(project=project, team=team, wiql=wiql, top=top)
        if not ids:
            return {"items": [], "totals": {"total": 0, "by_state": {}, "hours": {"original": 0.0, "remaining": 0.0, "completed": 0.0}}}

        fields = [
            "System.Id",
            "System.Title",
            "System.State",
            "System.WorkItemType",
            "System.AreaPath",
            "System.IterationPath",
            "System.AssignedTo",
            "Microsoft.VSTS.Scheduling.OriginalEstimate",
            "Microsoft.VSTS.Scheduling.RemainingWork",
            "Microsoft.VSTS.Scheduling.CompletedWork",
        ]
        work_items = self._get_work_items(ids, fields=fields, expand_relations=True)
        enriched = self._enrich_hierarchy(work_items)
        return self._build_snapshot(enriched)

    def _build_wiql(self, project: str, *, area_path: str | None, iteration_path: str | None) -> str:
        clauses = [
            f"[System.TeamProject] = '{project}'",
            "[System.WorkItemType] IN ('Epic', 'Feature', 'Product Backlog Item', 'User Story', 'Task', 'Bug')",
            "[System.State] <> 'Removed'",
        ]
        if area_path:
            clauses.append(f"[System.AreaPath] UNDER '{area_path}'")
        if iteration_path:
            clauses.append(f"[System.IterationPath] UNDER '{iteration_path}'")

        return (
            "SELECT [System.Id] "
            "FROM WorkItems "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY [System.ChangedDate] DESC"
        )

    def _run_wiql(self, *, project: str, team: str | None, wiql: str, top: int) -> list[int]:
        scope = f"{project}/{team}" if team else project
        url = f"{self.organization_url}/{scope}/_apis/wit/wiql"
        response = httpx.post(
            url,
            headers=self._headers,
            params={"api-version": self.api_version, "$top": max(1, min(top, 1000))},
            json={"query": wiql},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        refs = payload.get("workItems", []) if isinstance(payload, dict) else []
        return [int(item["id"]) for item in refs if isinstance(item, dict) and item.get("id")]

    def _get_work_items(self, ids: Iterable[int], *, fields: list[str], expand_relations: bool) -> list[dict[str, Any]]:
        id_list = [int(item) for item in ids]
        if not id_list:
            return []
        url = f"{self.organization_url}/_apis/wit/workitemsbatch"
        try:
            response = httpx.post(
                url,
                headers=self._headers,
                params={"api-version": self.api_version},
                json={
                    "ids": id_list,
                    "fields": fields,
                    "errorPolicy": "Omit",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            items = payload.get("value", []) if isinstance(payload, dict) else []
            if expand_relations:
                return self._load_relations_for_items(items)
            return items
        except httpx.HTTPStatusError as exc:
            # Some Azure DevOps tenants/process templates reject workitemsbatch with 400.
            # Fallback to GET /workitems in chunks to keep compatibility.
            if exc.response.status_code == 400:
                return self._get_work_items_fallback(id_list, fields=fields, expand_relations=expand_relations)
            raise

    def _get_work_items_fallback(self, ids: list[int], *, fields: list[str], expand_relations: bool) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        chunk_size = 200
        for start in range(0, len(ids), chunk_size):
            chunk = ids[start : start + chunk_size]
            base_params = {
                "api-version": self.api_version,
                "ids": ",".join(str(item) for item in chunk),
                "$expand": "Relations" if expand_relations else "None",
            }
            params_with_fields = {**base_params, "fields": ",".join(fields)}
            try:
                response = httpx.get(
                    f"{self.organization_url}/_apis/wit/workitems",
                    headers=self._headers,
                    params=params_with_fields,
                    timeout=self.timeout,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                # Some organizations/processes reject one or more requested fields.
                if exc.response.status_code != 400:
                    raise
                response = httpx.get(
                    f"{self.organization_url}/_apis/wit/workitems",
                    headers=self._headers,
                    params=base_params,
                    timeout=self.timeout,
                )
                response.raise_for_status()

            payload = response.json()
            values = payload.get("value", []) if isinstance(payload, dict) else []
            results.extend(values)
        return results

    def _load_relations_for_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        item_ids = [int(item["id"]) for item in items if item.get("id") is not None]
        if not item_ids:
            return items
        relation_items = self._get_work_items_fallback(item_ids, fields=["System.Id"], expand_relations=True)
        relation_map = {int(item["id"]): item.get("relations") or [] for item in relation_items if item.get("id") is not None}
        for item in items:
            item_id = int(item["id"]) if item.get("id") is not None else None
            if item_id is None:
                continue
            item["relations"] = relation_map.get(item_id, [])
        return items

    def _extract_parent_id(self, work_item: dict[str, Any]) -> int | None:
        relations = work_item.get("relations") or []
        for relation in relations:
            if relation.get("rel") != "System.LinkTypes.Hierarchy-Reverse":
                continue
            url = str(relation.get("url") or "")
            match = re.search(r"/workItems/(\d+)$", url)
            if match:
                return int(match.group(1))
        return None

    def _enrich_hierarchy(self, work_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not work_items:
            return []
        fields = [
            "System.Id",
            "System.Title",
            "System.State",
            "System.WorkItemType",
        ]

        parent_ids = {self._extract_parent_id(item) for item in work_items}
        parent_ids = {item for item in parent_ids if item is not None}
        parents = self._get_work_items(parent_ids, fields=fields, expand_relations=True) if parent_ids else []
        parent_map = {int(item.get("id")): item for item in parents if item.get("id")}

        grandparent_ids: set[int] = set()
        for parent in parents:
            grandparent_id = self._extract_parent_id(parent)
            if grandparent_id is not None:
                grandparent_ids.add(grandparent_id)
        grandparents = self._get_work_items(grandparent_ids, fields=fields, expand_relations=False) if grandparent_ids else []
        grandparent_map = {int(item.get("id")): item for item in grandparents if item.get("id")}

        output: list[dict[str, Any]] = []
        for work_item in work_items:
            item_id = int(work_item.get("id"))
            item_fields = work_item.get("fields") or {}
            parent_id = self._extract_parent_id(work_item)
            parent = parent_map.get(parent_id) if parent_id else None

            epic = None
            if parent:
                parent_fields = parent.get("fields") or {}
                if parent_fields.get("System.WorkItemType") == "Epic":
                    epic = parent
                else:
                    grandparent_id = self._extract_parent_id(parent)
                    if grandparent_id:
                        grandparent = grandparent_map.get(grandparent_id)
                        grandparent_fields = (grandparent or {}).get("fields") or {}
                        if grandparent_fields.get("System.WorkItemType") == "Epic":
                            epic = grandparent

            output.append(
                {
                    "id": item_id,
                    "type": item_fields.get("System.WorkItemType"),
                    "title": item_fields.get("System.Title"),
                    "state": item_fields.get("System.State"),
                    "area_path": item_fields.get("System.AreaPath"),
                    "iteration_path": item_fields.get("System.IterationPath"),
                    "assigned_to": self._normalize_identity(item_fields.get("System.AssignedTo")),
                    "hours": {
                        "original": self._to_float(item_fields.get("Microsoft.VSTS.Scheduling.OriginalEstimate")),
                        "remaining": self._to_float(item_fields.get("Microsoft.VSTS.Scheduling.RemainingWork")),
                        "completed": self._to_float(item_fields.get("Microsoft.VSTS.Scheduling.CompletedWork")),
                    },
                    "parent": self._map_linked_item(parent),
                    "epic": self._map_linked_item(epic),
                }
            )
        return output

    def _build_snapshot(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        by_state: dict[str, int] = {}
        total_original = 0.0
        total_remaining = 0.0
        total_completed = 0.0
        with_epic = 0

        for item in items:
            state = str(item.get("state") or "Unknown")
            by_state[state] = by_state.get(state, 0) + 1
            hours = item.get("hours") or {}
            total_original += self._to_float(hours.get("original"))
            total_remaining += self._to_float(hours.get("remaining"))
            total_completed += self._to_float(hours.get("completed"))
            if item.get("epic"):
                with_epic += 1

        diagnostics = self._build_diagnostics(items)

        return {
            "items": items,
            "totals": {
                "total": len(items),
                "with_epic": with_epic,
                "without_epic": len(items) - with_epic,
                "by_state": by_state,
                "hours": {
                    "original": round(total_original, 2),
                    "remaining": round(total_remaining, 2),
                    "completed": round(total_completed, 2),
                },
            },
            "diagnostics": diagnostics,
        }

    def _build_diagnostics(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        pbi_ids = {
            int(item["id"])
            for item in items
            if str(item.get("type") or "").strip() in PBI_TYPES
        }
        task_parent_ids = {
            int(item["parent"]["id"])
            for item in items
            if str(item.get("type") or "").strip() in TASK_TYPES and item.get("parent") and item["parent"].get("id") is not None
        }

        pbi_without_task = [
            item for item in items
            if str(item.get("type") or "").strip() in PBI_TYPES and int(item.get("id") or 0) in pbi_ids and int(item.get("id") or 0) not in task_parent_ids
        ]

        tasks_without_hours = []
        for item in items:
            if str(item.get("type") or "").strip() not in TASK_TYPES:
                continue
            state = str(item.get("state") or "").strip().lower()
            if state in DONE_STATES:
                continue
            hours = item.get("hours") or {}
            if self._to_float(hours.get("original")) == 0.0 and self._to_float(hours.get("remaining")) == 0.0 and self._to_float(hours.get("completed")) == 0.0:
                tasks_without_hours.append(item)

        return {
            "pbi_without_task": self._group_by_user(pbi_without_task),
            "tasks_without_hours": self._group_by_user(tasks_without_hours),
        }

    def _group_by_user(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        by_user: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            key = str(item.get("assigned_to") or "Sem responsavel").strip() or "Sem responsavel"
            by_user.setdefault(key, []).append(item)

        users = [
            {
                "user": user,
                "count": len(values),
                "items": [
                    {
                        "id": int(value.get("id")),
                        "title": value.get("title"),
                        "state": value.get("state"),
                        "type": value.get("type"),
                        "parent": value.get("parent"),
                        "epic": value.get("epic"),
                    }
                    for value in values
                ],
            }
            for user, values in sorted(by_user.items(), key=lambda entry: entry[0].lower())
        ]
        return {
            "total": len(items),
            "users": users,
        }

    def _normalize_identity(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            display_name = value.get("displayName")
            if display_name:
                return str(display_name)
            unique_name = value.get("uniqueName")
            if unique_name:
                return str(unique_name)
        return str(value)

    def _map_linked_item(self, item: dict[str, Any] | None) -> dict[str, Any] | None:
        if not item:
            return None
        fields = item.get("fields") or {}
        return {
            "id": int(item.get("id")),
            "type": fields.get("System.WorkItemType"),
            "title": fields.get("System.Title"),
            "state": fields.get("System.State"),
        }

    def _to_float(self, value: Any) -> float:
        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
