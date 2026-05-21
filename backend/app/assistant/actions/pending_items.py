from __future__ import annotations

from sqlalchemy.orm import Session

from app.assistant.actions.base import ActionResult, compact_items
from app.assistant.schemas import AssistantPlan
from app.models import PendingItem, User
from app.services.pending_item_service import PendingItemService


class PendingItemsAction:
    domain = "pending_items"

    def preview(self, db: Session, plan: AssistantPlan, user: User | None) -> dict:
        return {
            "title": "Pendencia",
            "action": plan.action,
            "params": plan.extracted_params,
            "missing_params": plan.missing_params,
            "impact": "A mudanca de status sera registrada no historico da pendencia.",
        }

    def execute(self, db: Session, plan: AssistantPlan, user: User | None) -> ActionResult:
        service = PendingItemService(db)
        if plan.action == "list":
            status = (plan.extracted_params or {}).get("status")
            items = service.list_items(status=status or None, limit=100)
            data = [
                {"id": item.id, "title": item.title, "status": item.status, "priority": item.priority, "responsible_id": item.responsible_id}
                for item in items
            ]
            return ActionResult(message=f"Encontrei {len(data)} pendencias.", data=compact_items(data))

        if plan.action in {"resolve", "ignore", "escalate"}:
            params = plan.extracted_params or {}
            item_id = params.get("pending_item_id")
            if not item_id:
                return ActionResult(message="Informe o ID da pendencia.", data={}, success=False, errors=["missing_pending_item_id"])
            item = db.query(PendingItem).filter(PendingItem.id == int(item_id)).first()
            if not item:
                return ActionResult(message="Pendencia nao encontrada.", data={}, success=False, errors=["pending_item_not_found"])
            note = params.get("comment")
            if plan.action == "resolve":
                item = service.resolve_item(item, note, user)
            elif plan.action == "ignore":
                item = service.ignore_item(item, note, user)
            else:
                item = service.escalate_item(item, note, user)
            return ActionResult(message=f"Pendencia {item.id} atualizada para {item.status}.", data={"id": item.id, "status": item.status})

        return ActionResult(message="Acao de pendencia nao suportada.", data={}, success=False, errors=["unsupported_action"])
