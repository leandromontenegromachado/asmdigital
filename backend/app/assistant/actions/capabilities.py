from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.assistant.actions.base import ActionResult
from app.assistant.schemas import AssistantPlan
from app.models import User


CAPABILITIES: list[dict[str, Any]] = [
    {"domain": "reports_ai", "label": "Relatorios IA", "actions": ["listar", "executar com confirmacao"]},
    {"domain": "reports_redmine", "label": "Relatorios Redmine", "actions": ["listar recentes", "executar com confirmacao"]},
    {"domain": "project_advisor", "label": "Agente consultivo", "actions": ["avaliar projetos Redmine", "somente leitura"]},
    {"domain": "routines", "label": "Rotinas", "actions": ["listar", "criar com confirmacao"]},
    {"domain": "notifications", "label": "Notificacoes", "actions": ["enviar com confirmacao"]},
    {"domain": "employees", "label": "Funcionarios", "actions": ["consultar", "cadastrar com confirmacao"]},
    {"domain": "management_events", "label": "Eventos Gerenciais", "actions": ["consultar status"]},
    {"domain": "pending_items", "label": "Pendencias", "actions": ["listar", "resolver/ignorar/escalar com confirmacao"]},
    {"domain": "evaluation", "label": "Avaliacao 360", "actions": ["consultar ciclos e status"]},
    {"domain": "chefia", "label": "ChefIA/FalaAI", "actions": ["consultar orientacoes"]},
    {"domain": "connectors", "label": "Conectores", "actions": ["consultar status"]},
    {"domain": "meetings", "label": "Agendamento de reunioes", "actions": ["agendar com confirmacao"]},
]


class CapabilitiesAction:
    domain = "general"

    def preview(self, db: Session, plan: AssistantPlan, user: User | None) -> dict[str, Any]:
        return {"capabilities": CAPABILITIES, "requires_confirmation": False}

    def execute(self, db: Session, plan: AssistantPlan, user: User | None) -> ActionResult:
        labels = ", ".join(item["label"] for item in CAPABILITIES)
        return ActionResult(message=f"Posso operar estas areas: {labels}.", data={"capabilities": CAPABILITIES})
