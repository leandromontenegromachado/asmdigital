from __future__ import annotations

from typing import Any

from app.adapters.azure_devops import AzureDevOpsAdapter
from app.models import Connector


AZURE_CONNECTOR_TYPES = {"azure", "azure_devops", "azure-devops"}


def _first_project(config_json: dict[str, Any]) -> str | None:
    direct = config_json.get("project")
    if direct:
        return str(direct).strip()
    project_ids = config_json.get("project_ids")
    if isinstance(project_ids, list):
        for value in project_ids:
            text = str(value).strip()
            if text:
                return text
    return None


def get_azure_adapter(connector: Connector) -> AzureDevOpsAdapter:
    if connector.type not in AZURE_CONNECTOR_TYPES:
        raise ValueError("Connector is not Azure DevOps")

    config = connector.config_json or {}
    organization_url = str(config.get("base_url") or "").strip()
    pat = str(config.get("api_key") or "").strip()
    if not organization_url or not pat:
        raise ValueError("Connector config missing base_url or api_key")
    return AzureDevOpsAdapter(organization_url=organization_url, personal_access_token=pat)


def resolve_project(connector: Connector, project_override: str | None) -> str:
    if project_override and project_override.strip():
        return project_override.strip()
    config = connector.config_json or {}
    project = _first_project(config)
    if project:
        return project
    raise ValueError("project is required")


def query_snapshot(
    connector: Connector,
    *,
    project: str | None,
    team: str | None = None,
    area_path: str | None = None,
    iteration_path: str | None = None,
    top: int = 200,
) -> dict[str, Any]:
    adapter = get_azure_adapter(connector)
    resolved_project = resolve_project(connector, project)
    return adapter.query_board_snapshot(
        project=resolved_project,
        team=team,
        area_path=area_path,
        iteration_path=iteration_path,
        top=top,
    )
