from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import ManagementEvent, ManagementEventAction, ManagementEventRule, PendingItem, User
from app.schemas.management_event_rules import ManagementEventRuleCreate, ManagementEventRuleUpdate
from app.services.management_event_service import ManagementEventService
from app.services.pending_item_service import PendingItemService

logger = logging.getLogger(__name__)


class ManagementEventRuleService:
    def __init__(self, db: Session):
        self.db = db

    def list_rules(self, active: bool | None = None, limit: int = 100) -> list[ManagementEventRule]:
        query = self.db.query(ManagementEventRule)
        if active is not None:
            query = query.filter(ManagementEventRule.is_active == active)
        return query.order_by(ManagementEventRule.priority.asc(), ManagementEventRule.id.asc()).limit(min(max(limit, 1), 500)).all()

    def get_rule(self, rule_id: int) -> ManagementEventRule | None:
        return self.db.query(ManagementEventRule).filter(ManagementEventRule.id == rule_id).first()

    def create_rule(self, payload: ManagementEventRuleCreate, actor: User) -> ManagementEventRule:
        rule = ManagementEventRule(**payload.model_dump(), created_by=actor.id)
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def update_rule(self, rule: ManagementEventRule, payload: ManagementEventRuleUpdate) -> ManagementEventRule:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(rule, key, value)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete_rule(self, rule: ManagementEventRule) -> None:
        rule.is_active = False
        self.db.commit()


class ManagementEventRuleEngine:
    OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "contains"}

    def __init__(self, db: Session):
        self.db = db

    def apply_rules(self, event: ManagementEvent, actor: User) -> dict[str, Any]:
        rules = (
            self.db.query(ManagementEventRule)
            .filter(ManagementEventRule.is_active.is_(True))
            .order_by(ManagementEventRule.priority.asc(), ManagementEventRule.id.asc())
            .all()
        )
        matched_rules = 0
        actions: list[ManagementEventAction] = []
        for rule in rules:
            if not self._matches(event, rule.condition_json or {}):
                continue
            matched_rules += 1
            for action_def in self._normalize_actions(rule.action_json or {}):
                actions.append(self._execute_action(event, rule, action_def, actor))
                self.db.refresh(event)
        return {
            "event_id": event.id,
            "matched_rules": matched_rules,
            "actions_executed": actions,
        }

    def _matches(self, event: ManagementEvent, condition: dict[str, Any]) -> bool:
        if not condition:
            return True
        if isinstance(condition.get("all"), list):
            return all(self._matches(event, item) for item in condition["all"] if isinstance(item, dict))
        if isinstance(condition.get("any"), list):
            return any(self._matches(event, item) for item in condition["any"] if isinstance(item, dict))
        if {"field", "op", "value"}.issubset(condition.keys()):
            return self._evaluate(event, condition["field"], condition["op"], condition["value"])
        return all(self._evaluate_field_spec(event, field, spec) for field, spec in condition.items())

    def _evaluate_field_spec(self, event: ManagementEvent, field: str, spec: Any) -> bool:
        if isinstance(spec, dict):
            return all(self._evaluate(event, field, op, value) for op, value in spec.items())
        return self._evaluate(event, field, "eq", spec)

    def _evaluate(self, event: ManagementEvent, field: str, op: str, expected: Any) -> bool:
        if op not in self.OPERATORS:
            logger.warning("management_event_rule_unknown_operator", extra={"operator": op, "field": field})
            return False
        actual = self._get_field_value(event, field)
        if op == "eq":
            return actual == expected
        if op == "neq":
            return actual != expected
        if op == "contains":
            return self._contains(actual, expected)
        return self._compare(actual, expected, op)

    def _get_field_value(self, event: ManagementEvent, field: str) -> Any:
        if hasattr(event, field):
            return getattr(event, field)
        payload = event.payload_json or {}
        if field.startswith("payload_json."):
            return self._get_nested(payload, field.removeprefix("payload_json."))
        return self._get_nested(payload, field)

    def _get_nested(self, data: dict[str, Any], path: str) -> Any:
        value: Any = data
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value

    def _contains(self, actual: Any, expected: Any) -> bool:
        if actual is None:
            return False
        if isinstance(actual, (list, tuple, set)):
            return expected in actual
        return str(expected).lower() in str(actual).lower()

    def _compare(self, actual: Any, expected: Any, op: str) -> bool:
        if actual is None:
            return False
        left, right = self._coerce_for_compare(actual, expected)
        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right
        if op == "lt":
            return left < right
        if op == "lte":
            return left <= right
        return False

    def _coerce_for_compare(self, actual: Any, expected: Any) -> tuple[Any, Any]:
        try:
            return float(actual), float(expected)
        except (TypeError, ValueError):
            return str(actual), str(expected)

    def _normalize_actions(self, action_json: dict[str, Any]) -> list[dict[str, Any]]:
        actions = action_json.get("actions")
        if isinstance(actions, list):
            return [action for action in actions if isinstance(action, dict)]
        if "type" in action_json or "action" in action_json:
            return [action_json]
        return []

    def _execute_action(
        self,
        event: ManagementEvent,
        rule: ManagementEventRule,
        action_def: dict[str, Any],
        actor: User,
    ) -> ManagementEventAction:
        action_type = str(action_def.get("type") or action_def.get("action") or "").strip()
        if action_type == "create_pending_item":
            item = PendingItemService(self.db).create_from_management_event(event, actor)
            return self._record_action(
                event,
                rule,
                action_def,
                action_type,
                status="executed",
                message=f"Pendencia #{item.id} criada.",
                pending_item=item,
                result_json={"pending_item_id": item.id},
            )
        if action_type == "mark_processed":
            ManagementEventService(self.db).process_event(event, action_def.get("note") or "Processado por regra gerencial.")
            return self._record_action(event, rule, action_def, action_type, status="executed", message="Evento marcado como processado.")
        if action_type == "ignore":
            ManagementEventService(self.db).ignore_event(event, action_def.get("note") or "Ignorado por regra gerencial.")
            return self._record_action(event, rule, action_def, action_type, status="executed", message="Evento marcado como ignorado.")
        if action_type == "notify_responsible":
            return self._record_action(
                event,
                rule,
                action_def,
                action_type,
                status="placeholder",
                message="Placeholder registrado. Nenhuma notificacao real foi enviada nesta fase.",
            )
        return self._record_action(
            event,
            rule,
            action_def,
            action_type or "unknown",
            status="error",
            message=f"Tipo de acao nao suportado: {action_type or '-'}",
        )

    def _record_action(
        self,
        event: ManagementEvent,
        rule: ManagementEventRule,
        action_def: dict[str, Any],
        action_type: str,
        *,
        status: str,
        message: str,
        pending_item: PendingItem | None = None,
        result_json: dict[str, Any] | None = None,
    ) -> ManagementEventAction:
        action = ManagementEventAction(
            rule_id=rule.id,
            management_event_id=event.id,
            pending_item_id=pending_item.id if pending_item else None,
            action_type=action_type,
            status=status,
            message=message,
            action_json=action_def,
            result_json=result_json or {},
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return action
