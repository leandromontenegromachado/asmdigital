from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.assistant.actions.base import ActionResult, compact_items
from app.assistant.schemas import AssistantPlan
from app.models import Automation, User
from app.services.automation_service import build_automation_key, next_run_from_cron, validate_cron_expression


class RoutinesAction:
    domain = "routines"

    def preview(self, db: Session, plan: AssistantPlan, user: User | None) -> dict[str, Any]:
        params = plan.extracted_params or {}
        return {
            "title": "Rotina",
            "action": plan.action,
            "params": params,
            "missing_params": plan.missing_params,
            "impact": "Criacao ou alteracao de rotina pode disparar execucoes futuras.",
        }

    def execute(self, db: Session, plan: AssistantPlan, user: User | None) -> ActionResult:
        if plan.action == "list":
            query = db.query(Automation)
            if (plan.extracted_params or {}).get("status") == "active":
                query = query.filter(Automation.is_enabled.is_(True))
            routines = query.order_by(Automation.id.asc()).limit(100).all()
            items = [
                {
                    "id": item.id,
                    "name": item.name,
                    "is_enabled": item.is_enabled,
                    "schedule_cron": item.schedule_cron,
                    "last_run_at": item.last_run_at.isoformat() if item.last_run_at else None,
                    "next_run_at": item.next_run_at.isoformat() if item.next_run_at else None,
                }
                for item in routines
            ]
            return ActionResult(message=f"Encontrei {len(items)} rotinas.", data=compact_items(items))

        if plan.action == "create":
            params = plan.extracted_params or {}
            name = str(params.get("name") or "Rotina criada pelo assistente").strip()
            schedule_cron = params.get("schedule_cron")
            if schedule_cron:
                validate_cron_expression(str(schedule_cron))
            existing_keys = {key for (key,) in db.query(Automation.key).all()}
            automation = Automation(
                key=build_automation_key(name, existing_keys),
                name=name,
                schedule_cron=schedule_cron,
                is_enabled=True,
                params_json={
                    "simulation": bool(params.get("simulation", True)),
                    "tasks": [str(task) for task in params.get("tasks") or []],
                    "notification_requested": bool(params.get("notification_requested", False)),
                    "created_by": "assistant",
                    "created_by_user_id": user.id if user else None,
                },
            )
            automation.next_run_at = next_run_from_cron(schedule_cron) if schedule_cron else None
            db.add(automation)
            db.commit()
            db.refresh(automation)
            return ActionResult(
                message=f"Rotina '{automation.name}' criada.",
                data={"id": automation.id, "name": automation.name, "schedule_cron": automation.schedule_cron},
            )

        return ActionResult(message="Acao de rotina nao suportada.", data={}, success=False, errors=["unsupported_action"])
