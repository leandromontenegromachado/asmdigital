from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from .advisor import evaluate_project
from .models import ProjectSnapshot
from .redmine_client import RedmineClient
from .render import render_markdown


AssistantOutput = Literal["dict", "markdown"]


def load_snapshot_from_file(path: str | Path) -> ProjectSnapshot:
    file_path = Path(path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return ProjectSnapshot.from_json(data)


def avaliar_projeto_redmine(
    *,
    project_id: int | str | None = None,
    input_path: str | Path | None = None,
    days_stale: int = 7,
    output: AssistantOutput = "dict",
    redmine_client: RedmineClient | None = None,
) -> dict[str, Any] | str:
    """Entry point for the existing assistant.

    This function is intentionally read-only. It either reads a local snapshot
    file for tests or fetches data from Redmine using GET requests only.
    """
    if bool(project_id) == bool(input_path):
        raise ValueError("Informe exatamente um: project_id ou input_path.")

    if input_path:
        snapshot = load_snapshot_from_file(input_path)
        source = {
            "type": "local_snapshot",
            "path": str(input_path),
        }
    else:
        client = redmine_client or RedmineClient.from_env()
        snapshot = client.get_project_snapshot(project_id or "")
        source = {
            "type": "redmine",
            "project_id": project_id,
            "read_only": True,
        }

    report = evaluate_project(snapshot, days_stale=days_stale)

    if output == "markdown":
        return render_markdown(report)

    return {
        "tool": "avaliar_projeto_redmine",
        "agent": "redmine_project_advisor",
        "read_only": True,
        "source": source,
        "days_stale": days_stale,
        "report": report.to_dict(),
        "assistant_guidance": {
            "use_as": "consultative_analysis",
            "do_not_post_to_redmine": True,
            "recommended_tone": "objetivo, consultivo e com evidencias",
        },
    }


def tool_definition() -> dict[str, Any]:
    """Generic tool schema your assistant can register."""
    return {
        "name": "avaliar_projeto_redmine",
        "description": (
            "Avalia um projeto do Redmine em modo somente leitura e retorna "
            "riscos, metricas, sugestoes e perguntas para o gestor."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": ["string", "integer"],
                    "description": "ID ou identificador do projeto no Redmine.",
                },
                "days_stale": {
                    "type": "integer",
                    "description": "Dias sem atualizacao para considerar uma issue parada.",
                    "default": 7,
                },
            },
            "required": ["project_id"],
            "additionalProperties": False,
        },
        "side_effects": "read_only",
    }
