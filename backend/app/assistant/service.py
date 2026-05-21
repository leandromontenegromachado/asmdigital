from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder
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
        plan = self._apply_conversation_context(command, plan, user)
        plan = self._complete_plan(plan, command.text)
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
        if action.status not in {"needs_confirmation", "needs_input"}:
            payload = action.payload_json or {}
            plan_payload = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
            return AssistantResponse(
                success=action.status in {"completed", "cancelled"},
                intent=plan_payload.get("intent"),
                domain=plan_payload.get("domain"),
                action=plan_payload.get("action") or action.action_type,
                message=f"Esta acao ja esta com status {action.status}.",
                preview=payload.get("preview") or {},
                data=action.result_json or {"status": action.status},
                errors=[] if action.status in {"completed", "cancelled"} else ["action_not_pending"],
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

        try:
            result = handler.execute(self.db, plan, user)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            action.status = "error"
            action.result_json = jsonable_encoder({"status": "error", "channel": channel, "error": str(exc)})
            action.confirmed_at = datetime.now(timezone.utc)
            self.db.commit()
            return AssistantResponse(
                success=False,
                intent=plan.intent,
                domain=plan.domain,
                action=plan.action,
                message=f"Nao consegui executar a acao: {exc}",
                preview=payload.get("preview") or {},
                data=action.result_json,
                errors=["execution_error"],
            )
        action.status = "completed" if result.success else "error"
        action.result_json = jsonable_encoder({"status": action.status, "channel": channel, **result.data, "errors": result.errors or []})
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

    def _complete_plan(self, plan: AssistantPlan, text: str) -> AssistantPlan:
        params = dict(plan.extracted_params or {})
        if plan.domain in {"reports_redmine", "reports_ai"} and plan.action == "run_report":
            params.setdefault("text", text)
        return plan.model_copy(update={"extracted_params": params})

    def _apply_conversation_context(self, command: AssistantCommand, plan: AssistantPlan, user: User | None) -> AssistantPlan:
        normalized = self._normalize_text(command.text)
        is_contextual = self._looks_contextual(normalized) or self._should_merge_report_context(normalized, plan)
        if not is_contextual:
            return plan

        previous = self._last_contextual_plan(command, user)
        if not previous:
            return plan

        previous_plan, previous_log_id = previous
        if previous_plan.domain not in {"reports_redmine", "reports_ai"}:
            return plan

        owner = self._corrected_owner(command.text)
        if not owner:
            if plan.domain in {"reports_redmine", "reports_ai"} and plan.action == "run_report":
                return self._merge_report_plan(previous_plan, plan, command.text, previous_log_id)
            if "redmine" in normalized or "demandas" in normalized or "demanda" in normalized:
                params = dict(previous_plan.extracted_params or {})
                params["text"] = self._combined_report_text(params.get("text"), command.text)
                params["context"] = {
                    "source": "follow_up",
                    "previous_command_log_id": previous_log_id,
                    "merged_fields": ["text", "owner", "status"],
                }
                return previous_plan.model_copy(
                    update={
                        "domain": "reports_redmine" if "redmine" in normalized else previous_plan.domain,
                        "action": "run_report",
                        "requires_confirmation": True,
                        "summary_for_user": "Vou continuar a ultima consulta e preparar o relatorio com o contexto anterior.",
                        "extracted_params": params,
                        "missing_params": [],
                    }
                )
            return previous_plan.model_copy(
                update={
                    "summary_for_user": "Entendi que voce quer continuar a ultima consulta. Vou preparar novamente com o contexto anterior.",
                    "extracted_params": {
                        **(previous_plan.extracted_params or {}),
                        "context": {"source": "previous_report", "previous_command_log_id": previous_log_id},
                    },
                }
            )

        params = dict(previous_plan.extracted_params or {})
        params["owner"] = owner
        params["text"] = self._report_prompt_with_owner(params, owner)
        params["context"] = {
            "source": "correction",
            "previous_command_log_id": previous_log_id,
            "corrected_field": "owner",
        }
        return previous_plan.model_copy(
            update={
                "requires_confirmation": True,
                "summary_for_user": f"Atualizei o responsavel para {owner} e vou preparar uma nova consulta ao Redmine para confirmacao.",
                "extracted_params": params,
                "missing_params": [],
            }
        )

    def _merge_report_plan(self, previous_plan: AssistantPlan, current_plan: AssistantPlan, text: str, previous_log_id: int) -> AssistantPlan:
        previous_params = dict(previous_plan.extracted_params or {})
        current_params = dict(current_plan.extracted_params or {})
        merged = {**previous_params, **{key: value for key, value in current_params.items() if self._has_value(value)}}
        for key in ("owner", "status", "template_id"):
            if not merged.get(key) and previous_params.get(key):
                merged[key] = previous_params[key]
        merged["text"] = self._combined_report_text(previous_params.get("text"), current_params.get("text") or text)
        merged["context"] = {
            "source": "follow_up",
            "previous_command_log_id": previous_log_id,
            "merged_fields": ["text", "owner", "status", "template_id"],
        }
        return current_plan.model_copy(
            update={
                "domain": "reports_redmine" if current_plan.domain == "reports_redmine" or "redmine" in self._normalize_text(text) else previous_plan.domain,
                "action": "run_report",
                "requires_confirmation": True,
                "summary_for_user": "Vou complementar a ultima consulta e preparar o relatorio para confirmacao.",
                "extracted_params": merged,
                "missing_params": [],
            }
        )

    def _last_contextual_plan(self, command: AssistantCommand, user: User | None) -> tuple[AssistantPlan, int] | None:
        user_id = command.user_id or (str(user.id) if user else None)
        query = self.db.query(AssistantCommandLog).filter(AssistantCommandLog.channel == command.channel)
        if user_id:
            query = query.filter(AssistantCommandLog.user_id == str(user_id))
        logs = query.order_by(AssistantCommandLog.created_at.desc()).limit(10).all()
        for log in logs:
            raw = log.raw_payload_json or {}
            plan_payload = raw.get("plan") if isinstance(raw.get("plan"), dict) else None
            if not plan_payload:
                continue
            try:
                previous_plan = AssistantPlan(**plan_payload)
            except Exception:
                continue
            if previous_plan.intent != AssistantIntent.UNKNOWN.value and previous_plan.domain != "general":
                return previous_plan, log.id
        return None

    def _looks_contextual(self, normalized_text: str) -> bool:
        markers = (
            "pode ser",
            "usar",
            "use",
            "fonte",
            "corrigi",
            "correcao",
            "corrigir",
            "errado",
            "na verdade",
            "o nome e",
            "nome correto",
            "quis dizer",
            "continua",
            "continuar",
            "sobre esse",
            "sobre este",
            "esse relatorio",
            "este relatorio",
        )
        return any(marker in normalized_text for marker in markers)

    def _should_merge_report_context(self, normalized_text: str, plan: AssistantPlan) -> bool:
        if plan.domain in {"reports_redmine", "reports_ai"} and plan.action == "run_report":
            params = plan.extracted_params or {}
            return not params.get("owner") or len(str(params.get("text") or "").split()) <= 8
        return any(term in normalized_text for term in ("redmine", "demandas", "demanda", "relatorio", "relatorio"))

    def _corrected_owner(self, text: str) -> str | None:
        patterns = [
            r"(?:nome|respons[aá]vel|usuario|usu[aá]rio)\s+(?:correto\s+)?(?:e|é|eh)\s+(.+)$",
            r"(?:quis dizer|na verdade(?:\s+e|\s+é|\s+eh)?|corrigir para|corrija para)\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = re.split(r"\s+(?:no|na|do|da)\s+(?:redmine|relat[oó]rio)\b", match.group(1).strip(" ."), maxsplit=1, flags=re.IGNORECASE)[0]
                return value[:120].strip(" .") or None
        return None

    def _report_prompt_with_owner(self, params: dict[str, Any], owner: str) -> str:
        status = str(params.get("status") or "").strip().lower()
        status_text = "em aberto" if status in {"open", "opened", "aberto", "abertos"} else status
        parts = ["Liste as demandas do Redmine"]
        if status_text:
            parts.append(status_text)
        parts.append(f"do responsavel {owner}")
        return " ".join(parts) + "."

    def _combined_report_text(self, previous_text: Any, current_text: Any) -> str:
        previous = str(previous_text or "").strip()
        current = str(current_text or "").strip()
        if previous and current and self._normalize_text(current) not in self._normalize_text(previous):
            return f"{previous}. Complemento: {current}"
        return current or previous

    def _normalize_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return " ".join(normalized.lower().strip().split())

    def _has_value(self, value: Any) -> bool:
        return value is not None and value != "" and value != []

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
