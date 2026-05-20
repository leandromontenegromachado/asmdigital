from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.assistant.actions.list_late_projects import format_late_projects_message, list_late_projects
from app.assistant.actions.notify_responsibles import build_notify_responsibles_confirmation
from app.assistant.intent_router import AssistantIntent, detect_intent
from app.assistant.permissions import can_execute
from app.assistant.schemas import AssistantCommand, AssistantResponse
from app.models import AssistantAction, AssistantCommandLog, AssistantConversation, User


class AssistantCoreService:
    def __init__(self, db: Session):
        self.db = db

    def process_command(self, command: AssistantCommand, user: User | None = None) -> AssistantResponse:
        intent = detect_intent(command.text)
        if intent == AssistantIntent.CREATE_MEETING:
            response = AssistantResponse(
                success=False,
                intent=intent.value,
                action="legacy_assistant_service",
                message="LEGACY_ASSISTANT_FALLBACK",
            )
            self._log(command, response, intent.value, "legacy_assistant_service")
            return response

        if not can_execute(user, intent.value):
            response = AssistantResponse(
                success=False,
                intent=intent.value,
                action=intent.value,
                message="Voce nao tem permissao para executar esta acao.",
                errors=["permission_denied"],
            )
            self._log(command, response, intent.value, intent.value)
            return response

        if intent == AssistantIntent.HELP:
            response = self._help_response()
        elif intent == AssistantIntent.LIST_LATE_PROJECTS:
            response = self._list_late_projects_response()
        elif intent == AssistantIntent.NOTIFY_RESPONSIBLES:
            response = self._notify_responsibles_response(command, user)
        else:
            response = AssistantResponse(
                success=False,
                intent=AssistantIntent.UNKNOWN.value,
                action=None,
                message="Nao entendi o pedido. Tente: listar projetos em atraso ou notificar responsaveis dos projetos atrasados.",
                errors=["unknown_intent"],
            )

        self._log(command, response, response.intent, response.action)
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
        if not confirmed:
            action.status = "cancelled"
            action.result_json = {"status": "cancelled", "channel": channel}
            self.db.commit()
            return AssistantResponse(success=True, action=action.action_type, message="Acao cancelada.", data=action.result_json)

        if action.action_type == AssistantIntent.NOTIFY_RESPONSIBLES.value:
            payload = action.payload_json or {}
            result = {
                "status": "simulated",
                "recipients": payload.get("recipients") or [],
                "notified_at": datetime.now(timezone.utc).isoformat(),
                "channel": channel,
            }
            action.status = "completed"
            action.result_json = result
            action.confirmed_at = datetime.now(timezone.utc)
            self.db.commit()
            return AssistantResponse(
                success=True,
                action=action.action_type,
                message=f"Notificacao simulada para {len(result['recipients'])} responsaveis.",
                data=result,
            )

        return AssistantResponse(
            success=False,
            action=action.action_type,
            message="Esta confirmacao ainda nao possui executor configurado.",
            errors=["unsupported_confirmation_action"],
        )

    def _help_response(self) -> AssistantResponse:
        return AssistantResponse(
            success=True,
            intent=AssistantIntent.HELP.value,
            action="HELP",
            message=(
                "Posso ajudar com: listar projetos em atraso, notificar responsaveis dos projetos atrasados "
                "e encaminhar pedidos de reuniao para o fluxo de agendamento."
            ),
        )

    def _list_late_projects_response(self) -> AssistantResponse:
        data = list_late_projects()
        return AssistantResponse(
            success=True,
            intent=AssistantIntent.LIST_LATE_PROJECTS.value,
            action=AssistantIntent.LIST_LATE_PROJECTS.value,
            message=format_late_projects_message(data),
            data=data,
        )

    def _notify_responsibles_response(self, command: AssistantCommand, user: User | None) -> AssistantResponse:
        payload = build_notify_responsibles_confirmation()
        conversation = self._conversation(command, user)
        action = AssistantAction(
            conversation_id=conversation.id,
            user_id=user.id if user else None,
            action_type=AssistantIntent.NOTIFY_RESPONSIBLES.value,
            status="needs_confirmation",
            payload_json=payload,
            result_json={},
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return AssistantResponse(
            success=True,
            intent=AssistantIntent.NOTIFY_RESPONSIBLES.value,
            action=AssistantIntent.NOTIFY_RESPONSIBLES.value,
            message=f"{payload['message_preview']} Responda confirmando pelo endpoint de confirmacao.",
            requires_confirmation=True,
            confirmation_id=f"assistant_action:{action.id}",
            data=payload,
        )

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

    def _log(self, command: AssistantCommand, response: AssistantResponse, intent: str | None, action: str | None) -> None:
        self.db.add(
            AssistantCommandLog(
                user_id=command.user_id,
                user_name=command.user_name,
                channel=command.channel,
                text=command.text,
                intent=intent,
                action=action,
                response_message=response.message,
                success=response.success,
                raw_payload_json={"raw_payload": command.raw_payload, "metadata": command.metadata},
            )
        )
        self.db.commit()
