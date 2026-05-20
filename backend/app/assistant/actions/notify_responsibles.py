from __future__ import annotations

from typing import Any

from app.assistant.actions.list_late_projects import list_late_projects


def build_notify_responsibles_confirmation() -> dict[str, Any]:
    late_projects = list_late_projects()
    recipients = sorted({item["responsible"] for item in late_projects.get("items", [])})
    return {
        "late_projects": late_projects,
        "recipients": recipients,
        "message_preview": (
            f"Encontrei {late_projects['total']} projetos atrasados para {len(recipients)} responsaveis. "
            "Deseja enviar notificacao para os responsaveis?"
        ),
    }
