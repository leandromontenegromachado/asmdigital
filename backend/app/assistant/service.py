from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.assistant.actions.capabilities import CAPABILITIES
from app.assistant.actions.registry import get_action_handler
from app.assistant.intent_router import AssistantIntent, interpret_command
from app.assistant.permissions import can_execute
from app.assistant.schemas import AssistantCommand, AssistantHistoryItem, AssistantPlan, AssistantResponse
from app.models import AssistantAction, AssistantCommandLog, AssistantConversation, User


class AssistantCoreService:
    def __init__(self, db: Session):
        self.db = db

    def process_command(self, command: AssistantCommand, user: User | None = None) -> AssistantResponse:
        plan = interpret_command(command.text, self.db)
        if plan.intent == AssistantIntent.CREATE_MEETING.value:
            response = AssistantResponse(
                success=False,
                intent=plan.intent,
                domain=plan.domain,
                action="legacy_assistant_service",
                message="LEGACY_ASSISTANT_FALLBACK",
                preview=self._preview_from_plan(plan),
            )
            self._log(command, response, plan)
            return response

        if not can_execute(user, plan.domain, plan.action):
            response = AssistantResponse(
                success=False,
                intent=plan.intent,
                domain=plan.domain,
                action=plan.action,
                message="Voce nao tem permissao para executar esta acao.",
                preview=self._preview_from_plan(plan),
                missing_params=plan.missing_params,
                errors=["permission_denied"],
            )
            self._log(command, response, plan)
            return response

        handler = get_action_handler(plan.domain)
        if not handler:
            response = AssistantResponse(
                success=False,
                intent=plan.intent,
                domain=plan.domain,
                action=plan.action,
                message="Ainda nao tenho executor para essa funcionalidade.",
                preview=self._preview_from_plan(plan),
                missing_params=plan.missing_params,
                errors=["unsupported_domain"],
            )
            self._log(command, response, plan)
            return response

        preview = handler.preview(self.db, plan, user)
        if plan.missing_params:
            response = AssistantResponse(
                success=True,
                intent=plan.intent,
                domain=plan.domain,
                action=plan.action,
                message=f"{plan.summary_for_user} Ainda faltam dados: {', '.join(plan.missing_params)}.",
                requires_confirmation=plan.requires_confirmation,
                preview=preview,
                missing_params=plan.missing_params,
            )
            self._log(command, response, plan)
            return response

        if plan.requires_confirmation:
            action = self._create_pending_action(command, user, plan, preview)
            response = AssistantResponse(
                success=True,
                intent=plan.intent,
                domain=plan.domain,
                action=plan.action,
                message=plan.summary_for_user,
                requires_confirmation=True,
                confirmation_id=f"assistant_action:{action.id}",
                preview=preview,
                missing_params=plan.missing_params,
                data={"action_id": action.id, "status": action.status},
            )
            self._log(command, response, plan)
            return response

        result = handler.execute(self.db, plan, user)
        response = AssistantResponse(
            success=result.success,
            intent=plan.intent,
            domain=plan.domain,
            action=plan.action,
            message=result.message,
            preview=preview,
            data=result.data,
            errors=result.errors or [],
        )
        self._log(command, response, plan, result=result.data)
        return response

    def confirm(self, confirmation_id: str, confirmed: bool, user: User | None = None, channel: str = "web") -> AssistantResponse:
        action = self._action_from_confirmation_id(confirmation_id)
        if not action:
            return AssistantResponse(
                success=False,
                action="confirm",
                message="Confirmacao nao encontrada.",
                errors=["confirmation_not_found"],
            )
        if action.user_id and user and action.user_id != user.id and (user.role or "").lower() not in {"admin", "gerente"}:
            return AssistantResponse(
                success=False,
                action=action.action_type,
                message="Voce nao tem permissao para confirmar esta acao.",
                errors=["permission_denied"],
            )
        payload = action.payload_json or {}
        plan = AssistantPlan(**(payload.get("plan") or {}))
        if not can_execute(user, plan.domain, plan.action):
            return AssistantResponse(
                success=False,
                intent=plan.intent,
                domain=plan.domain,
                action=plan.action,
                message="Voce nao tem permissao para executar esta acao.",
                errors=["permission_denied"],
            )

        if not confirmed:
            action.status = "cancelled"
            action.result_json = {"status": "cancelled", "channel": channel}
            self.db.commit()
            return AssistantResponse(
                success=True,
                intent=plan.intent,
                domain=plan.domain,
                action=plan.action,
                message="Acao cancelada.",
                data=action.result_json,
            )

        handler = get_action_handler(plan.domain)
        if not handler:
            return AssistantResponse(
                success=False,
                intent=plan.intent,
                domain=plan.domain,
                action=plan.action,
                message="Esta confirmacao ainda nao possui executor configurado.",
                errors=["unsupported_confirmation_action"],
            )

        result = handler.execute(self.db, plan, user)
        action.status = "completed" if result.success else "error"
        action.result_json = {"status": action.status, "channel": channel, **result.data, "errors": result.errors or []}
        action.confirmed_at = datetime.now(timezone.utc)
        self.db.commit()
        return AssistantResponse(
            success=result.success,
            intent=plan.intent,
            domain=plan.domain,
            action=plan.action,
            message=result.message,
            preview=payload.get("preview") or {},
            data=action.result_json,
            errors=result.errors or [],
        )

    def history(self, user: User | None = None, limit: int = 50) -> list[AssistantHistoryItem]:
        query = self.db.query(AssistantCommandLog)
        if user and (user.role or "").lower() not in {"admin", "gerente"}:
            query = query.filter(AssistantCommandLog.user_id == str(user.id))
        logs = query.order_by(AssistantCommandLog.created_at.desc()).limit(min(max(limit, 1), 200)).all()
        items = []
        for log in logs:
            raw = log.raw_payload_json or {}
            plan = raw.get("plan") if isinstance(raw.get("plan"), dict) else {}
            items.append(
                AssistantHistoryItem(
                    id=log.id,
                    user_id=log.user_id,
                    user_name=log.user_name,
                    channel=log.channel,
                    text=log.text,
                    intent=log.intent,
                    domain=plan.get("domain"),
                    action=log.action,
                    response_message=log.response_message,
                    success=log.success,
                    raw_payload_json=raw,
                    created_at=log.created_at,
                )
            )
        return items

    def capabilities(self) -> dict[str, Any]:
        return {"capabilities": CAPABILITIES}

    def _create_pending_action(
        self,
        command: AssistantCommand,
        user: User | None,
        plan: AssistantPlan,
        preview: dict[str, Any],
    ) -> AssistantAction:
        conversation = self._conversation(command, user)
        action = AssistantAction(
            conversation_id=conversation.id,
            user_id=user.id if user else None,
            action_type=f"{plan.domain}.{plan.action}",
            status="needs_confirmation",
            payload_json={"plan": plan.model_dump(), "preview": preview, "original_text": command.text},
            result_json={},
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return action

    def _conversation(self, command: AssistantCommand, user: User | None) -> AssistantConversation:
        external_chat_id = str(command.metadata.get("chat_id") or "") or None
        query = self.db.query(AssistantConversation).filter(AssistantConversation.channel == command.channel)
        conversation = None
        if external_chat_id:
            conversation = query.filter(AssistantConversation.external_chat_id == external_chat_id).first()
        elif user:
            conversation = query.filter(AssistantConversation.user_id == user.id).first()
        if conversation:
            return conversation
        conversation = AssistantConversation(
            channel=command.channel,
            external_chat_id=external_chat_id,
            user_id=user.id if user else None,
            state_json={},
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def _action_from_confirmation_id(self, confirmation_id: str) -> AssistantAction | None:
        raw_id = str(confirmation_id or "").replace("assistant_action:", "").strip()
        if not raw_id.isdigit():
            return None
        return self.db.query(AssistantAction).filter(AssistantAction.id == int(raw_id)).first()

    def _preview_from_plan(self, plan: AssistantPlan) -> dict[str, Any]:
        return {
            "summary": plan.summary_for_user,
            "params": plan.extracted_params,
            "missing_params": plan.missing_params,
            "risk_level": plan.risk_level,
            "permission_required": plan.permission_required,
            "requires_confirmation": plan.requires_confirmation,
        }

    def _log(
        self,
        command: AssistantCommand,
        response: AssistantResponse,
        plan: AssistantPlan,
        result: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            AssistantCommandLog(
                user_id=command.user_id,
                user_name=command.user_name,
                channel=command.channel,
                text=command.text,
                intent=plan.intent,
                action=plan.action,
                response_message=response.message,
                success=response.success,
                raw_payload_json={
                    "raw_payload": command.raw_payload,
                    "metadata": command.metadata,
                    "plan": plan.model_dump(),
                    "preview": response.preview,
                    "confirmation_id": response.confirmation_id,
                    "result": result or response.data,
                    "errors": response.errors,
                },
            )
        )
        self.db.commit()
