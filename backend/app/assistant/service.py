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
from app.assistant.knowledge import AssistantKnowledgeService
from app.assistant.permissions import can_execute
from app.assistant.schemas import AssistantCommand, AssistantHistoryItem, AssistantPlan, AssistantResponse
from app.models import AssistantAction, AssistantCommandLog, AssistantConversation, User


class AssistantCoreService:
    def __init__(self, db: Session):
        self.db = db

    def process_command(self, command: AssistantCommand, user: User | None = None) -> AssistantResponse:
        knowledge_context = self._knowledge_context(command.text)
        plan = interpret_command(command.text, self.db, knowledge_context=knowledge_context)

        pending_input = self._pending_input_action(command, user)
        if pending_input:
            if not plan.should_execute:
                response = self._response_from_non_executable_plan(command, plan, user)
                self._log(command, response, plan, result=response.data)
            elif self._should_continue_pending_input(command.text, pending_input):
                response = self._continue_pending_input(command, pending_input, user)
            else:
                response = self._pending_input_reminder(command, pending_input)
            if response:
                return response

        conversational_response = self._conversational_response(command, user) if self._is_greeting(self._normalize_text(command.text)) else None
        if conversational_response:
            plan = AssistantPlan(
                intent=conversational_response.intent or "knowledge_answer",
                domain=conversational_response.domain or "general",
                action=conversational_response.action or "knowledge_answer",
                confidence=0.95,
            )
            self._log(command, conversational_response, plan, result=conversational_response.data)
            return conversational_response

        plan = self._apply_conversation_context(command, plan, user)
        plan = self._complete_plan(plan, command.text)
        if not plan.should_execute:
            response = self._response_from_non_executable_plan(command, plan, user)
            self._log(command, response, plan, result=response.data)
            return response
        knowledge_response = self._knowledge_response(command, plan, user)
        if knowledge_response:
            self._log(command, knowledge_response, plan, result=knowledge_response.data)
            return knowledge_response
        if plan.intent == AssistantIntent.CREATE_MEETING.value or (plan.domain == "meetings" and plan.action in {"create", "schedule"}):
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
            action = self._create_pending_action(command, user, plan, preview, status="needs_input")
            response = AssistantResponse(
                success=True,
                intent=plan.intent,
                domain=plan.domain,
                action=plan.action,
                message=self._missing_input_message(plan),
                requires_confirmation=plan.requires_confirmation,
                confirmation_id=f"assistant_action:{action.id}",
                preview=preview,
                missing_params=plan.missing_params,
                data={"action_id": action.id, "status": action.status},
            )
            self._log(command, response, plan)
            return response

        if plan.requires_confirmation:
            action = self._create_pending_action(command, user, plan, preview, status="needs_confirmation")
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
        if action.status == "needs_input" and plan.missing_params:
            return AssistantResponse(
                success=True,
                intent=plan.intent,
                domain=plan.domain,
                action=plan.action,
                message=self._missing_input_message(plan),
                requires_confirmation=plan.requires_confirmation,
                confirmation_id=f"assistant_action:{action.id}",
                preview=payload.get("preview") or {},
                missing_params=plan.missing_params,
                data={"action_id": action.id, "status": action.status},
            )
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

    def seed_knowledge(self) -> dict[str, Any]:
        count = AssistantKnowledgeService(self.db).ensure_seeded()
        return {"created": count}

    def search_knowledge(self, query: str, limit: int = 5) -> dict[str, Any]:
        hits = AssistantKnowledgeService(self.db).search(query, limit=limit)
        return {"total": len(hits), "items": [hit.__dict__ for hit in hits]}

    def _create_pending_action(
        self,
        command: AssistantCommand,
        user: User | None,
        plan: AssistantPlan,
        preview: dict[str, Any],
        status: str = "needs_confirmation",
    ) -> AssistantAction:
        conversation = self._conversation(command, user)
        action = AssistantAction(
            conversation_id=conversation.id,
            user_id=user.id if user else None,
            action_type=f"{plan.domain}.{plan.action}",
            status=status,
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

    def _pending_input_action(self, command: AssistantCommand, user: User | None) -> AssistantAction | None:
        if self._db_is_mock():
            return None
        conversation = self._conversation(command, user)
        return (
            self.db.query(AssistantAction)
            .filter(AssistantAction.conversation_id == conversation.id, AssistantAction.status == "needs_input")
            .order_by(AssistantAction.id.desc())
            .first()
        )

    def _continue_pending_input(self, command: AssistantCommand, action: AssistantAction, user: User | None) -> AssistantResponse | None:
        payload = action.payload_json or {}
        plan_payload = payload.get("plan") if isinstance(payload.get("plan"), dict) else None
        if not plan_payload:
            return None
        try:
            previous_plan = AssistantPlan(**plan_payload)
        except Exception:
            return None

        normalized = self._normalize_text(command.text)
        if normalized in {"cancelar", "cancela", "nao", "não", "desiste"}:
            action.status = "cancelled"
            action.result_json = {"status": "cancelled"}
            self.db.commit()
            response = AssistantResponse(
                success=True,
                intent=previous_plan.intent,
                domain=previous_plan.domain,
                action=previous_plan.action,
                message="Acao cancelada.",
                data=action.result_json,
            )
            self._log(command, response, previous_plan, result=response.data)
            return response

        knowledge_context = self._knowledge_context(command.text)
        current_plan = interpret_command(command.text, self.db, knowledge_context=knowledge_context)
        updated_plan = self._merge_pending_plan(previous_plan, current_plan, command.text)
        updated_plan = self._complete_plan(updated_plan, command.text)

        if not can_execute(user, updated_plan.domain, updated_plan.action):
            response = AssistantResponse(
                success=False,
                intent=updated_plan.intent,
                domain=updated_plan.domain,
                action=updated_plan.action,
                message="Voce nao tem permissao para executar esta acao.",
                errors=["permission_denied"],
            )
            self._log(command, response, updated_plan)
            return response

        handler = get_action_handler(updated_plan.domain)
        if not handler:
            return None

        preview = handler.preview(self.db, updated_plan, user)
        action.payload_json = {
            **payload,
            "plan": updated_plan.model_dump(),
            "preview": preview,
            "last_input_text": command.text,
        }

        if updated_plan.missing_params:
            action.status = "needs_input"
            self.db.commit()
            response = AssistantResponse(
                success=True,
                intent=updated_plan.intent,
                domain=updated_plan.domain,
                action=updated_plan.action,
                message=self._missing_input_message(updated_plan),
                requires_confirmation=updated_plan.requires_confirmation,
                confirmation_id=f"assistant_action:{action.id}",
                preview=preview,
                missing_params=updated_plan.missing_params,
                data={"action_id": action.id, "status": action.status},
            )
            self._log(command, response, updated_plan)
            return response

        if updated_plan.requires_confirmation:
            action.status = "needs_confirmation"
            self.db.commit()
            response = AssistantResponse(
                success=True,
                intent=updated_plan.intent,
                domain=updated_plan.domain,
                action=updated_plan.action,
                message=f"Atualizei as informacoes. Revise a previa e confirme para executar.",
                requires_confirmation=True,
                confirmation_id=f"assistant_action:{action.id}",
                preview=preview,
                data={"action_id": action.id, "status": action.status},
            )
            self._log(command, response, updated_plan)
            return response

        result = handler.execute(self.db, updated_plan, user)
        action.status = "completed" if result.success else "error"
        action.result_json = jsonable_encoder({"status": action.status, **result.data, "errors": result.errors or []})
        self.db.commit()
        response = AssistantResponse(
            success=result.success,
            intent=updated_plan.intent,
            domain=updated_plan.domain,
            action=updated_plan.action,
            message=result.message,
            preview=preview,
            data=result.data,
            errors=result.errors or [],
        )
        self._log(command, response, updated_plan, result=result.data)
        return response

    def _merge_pending_plan(self, previous_plan: AssistantPlan, current_plan: AssistantPlan, text: str) -> AssistantPlan:
        previous_params = dict(previous_plan.extracted_params or {})
        current_params = dict(current_plan.extracted_params or {})
        if current_plan.domain == previous_plan.domain and current_plan.action == previous_plan.action:
            for key, value in current_params.items():
                if self._has_value(value):
                    previous_params[key] = value

        updates = self._params_from_input_text(text, previous_plan.missing_params, previous_params)
        previous_params.update(updates)
        missing = [field for field in previous_plan.missing_params if not self._has_value(previous_params.get(field))]
        return previous_plan.model_copy(update={"extracted_params": previous_params, "missing_params": missing})

    def _params_from_input_text(self, text: str, missing_params: list[str], existing_params: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        normalized_missing = [str(field) for field in missing_params]
        email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
        if email_match and "email" in normalized_missing:
            updates["email"] = email_match.group(0).lower()
        int_match = re.search(r"\b(\d+)\b", text)
        for field in normalized_missing:
            lowered = field.lower()
            field_pattern = re.search(rf"\b{re.escape(lowered)}\b\s*(?:e|eh|é|:|=|para)\s+(.+)$", text, flags=re.IGNORECASE)
            if field_pattern:
                updates[field] = field_pattern.group(1).strip(" .")
                continue
            if lowered in {"pending_item_id", "template_id", "id"} and int_match:
                updates[field] = int(int_match.group(1))
                continue
            if lowered in {"comment", "comentario"}:
                updates[field] = text.strip()
                continue
            if lowered in {"employee_name", "owner", "name", "title", "target", "channel", "source"} and not existing_params.get(field):
                updates[field] = text.strip(" .")
        if len(normalized_missing) == 1 and normalized_missing[0] not in updates:
            field = normalized_missing[0]
            if field == "email" and not email_match:
                return updates
            updates[field] = text.strip(" .")
        return {key: value for key, value in updates.items() if self._has_value(value)}

    def _missing_input_message(self, plan: AssistantPlan) -> str:
        missing = ", ".join(plan.missing_params)
        return (
            f"{plan.summary_for_user} Ainda faltam dados: {missing}. "
            "Envie uma nova mensagem com essas informacoes ou corrija algum campo. "
            "Voce tambem pode responder 'cancelar'."
        )

    def _should_continue_pending_input(self, text: str, action: AssistantAction) -> bool:
        normalized = self._normalize_text(text)
        if self._is_greeting(normalized) or self._is_information_question(text):
            return False
        if normalized in {"cancelar", "cancela", "nao", "não", "desiste"}:
            return True

        payload = action.payload_json or {}
        plan_payload = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
        missing = [str(item) for item in plan_payload.get("missing_params") or []]

        if self._looks_contextual(normalized):
            return True
        if any(field.lower() in normalized for field in missing):
            return True
        if "email" in missing and re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text):
            return True
        if any(field in {"pending_item_id", "template_id", "id"} for field in missing) and re.search(r"\b\d+\b", text):
            return True
        return bool(missing) and not normalized.startswith(
            ("consegue", "pode", "vc pode", "vc consegue", "voce pode", "voce consegue", "você pode", "você consegue", "como ", "o que ")
        )

    def _pending_input_reminder(self, command: AssistantCommand, action: AssistantAction) -> AssistantResponse:
        payload = action.payload_json or {}
        plan = AssistantPlan(**(payload.get("plan") or {}))
        response = AssistantResponse(
            success=True,
            intent=plan.intent,
            domain=plan.domain,
            action=plan.action,
            message=self._missing_input_message(plan),
            requires_confirmation=plan.requires_confirmation,
            confirmation_id=f"assistant_action:{action.id}",
            preview=payload.get("preview") or {},
            missing_params=plan.missing_params,
            data={"action_id": action.id, "status": action.status},
        )
        self._log(command, response, plan)
        return response

    def _knowledge_context(self, text: str) -> str:
        if self._db_is_mock():
            return ""
        try:
            return AssistantKnowledgeService(self.db).context_for_prompt(text, limit=5)
        except Exception:
            return ""

    def _response_from_non_executable_plan(self, command: AssistantCommand, plan: AssistantPlan, user: User | None) -> AssistantResponse:
        message = (plan.answer_to_user or "").strip()
        data: dict[str, Any] = {"message_type": plan.message_type}
        if plan.action == "capabilities":
            labels = ", ".join(item["label"] for item in CAPABILITIES)
            if message:
                message = f"{message}\n\nAreas que conheco: {labels}."
            else:
                message = f"Posso operar estas areas: {labels}."
            data["capabilities"] = CAPABILITIES
        if not message and not self._db_is_mock():
            try:
                answer = AssistantKnowledgeService(self.db).answer_question(command.text, user=user)
            except Exception:
                answer = None
            if answer:
                message, knowledge_data = answer
                data.update(knowledge_data)
        if not message:
            message = "Posso responder duvidas sobre o ASM Digital ou preparar acoes quando voce pedir uma execucao especifica."
        return AssistantResponse(
            success=True,
            intent=plan.intent,
            domain=plan.domain,
            action=plan.action if plan.action != "unknown" else "answer",
            message=message,
            data=data,
        )

    def _conversational_response(self, command: AssistantCommand, user: User | None) -> AssistantResponse | None:
        normalized = self._normalize_text(command.text)
        if self._is_greeting(normalized):
            name = (getattr(user, "name", None) or command.user_name or "").strip()
            greeting = f"Ola, {name}." if name else "Ola."
            return AssistantResponse(
                success=True,
                intent="greeting",
                domain="general",
                action="answer",
                message=(
                    f"{greeting} Posso responder duvidas sobre o ASM Digital ou operar funcionalidades do sistema. "
                    "Quando uma acao alterar dados, eu mostro a previa e peco confirmacao antes de executar."
                ),
            )

        if not self._is_information_question(command.text):
            return None

        capability = self._capability_question_answer(normalized)
        if capability:
            return AssistantResponse(
                success=True,
                intent="capability_question",
                domain="general",
                action="answer",
                message=capability,
                data={"source": "capability_router"},
            )

        if self._db_is_mock():
            return AssistantResponse(
                success=True,
                intent="knowledge_answer",
                domain="general",
                action="answer",
                message="Posso explicar o funcionamento do ASM Digital e orientar o uso das telas. Para executar acoes, descreva a acao desejada.",
            )

        try:
            answer = AssistantKnowledgeService(self.db).answer_question(command.text, user=user)
        except Exception:
            answer = None
        if not answer:
            return AssistantResponse(
                success=True,
                intent="knowledge_answer",
                domain="general",
                action="answer",
                message="Posso ajudar com duvidas sobre o ASM Digital. Pergunte sobre uma tela, modulo ou funcionalidade, ou peca uma acao especifica para eu preparar.",
            )
        message, data = answer
        return AssistantResponse(
            success=True,
            intent="knowledge_answer",
            domain="general",
            action="answer",
            message=message,
            data=data,
        )

    def _is_greeting(self, normalized_text: str) -> bool:
        greetings = {
            "oi",
            "ola",
            "olá",
            "bom dia",
            "boa tarde",
            "boa noite",
            "tudo bem",
            "bom dia tudo bem",
            "boa tarde tudo bem",
            "boa noite tudo bem",
        }
        return normalized_text.strip(" ?!.") in greetings

    def _is_information_question(self, text: str) -> bool:
        normalized = self._normalize_text(text)
        if not normalized:
            return False
        direct_request_markers = (
            "me liste",
            "me listar",
            "me mostra",
            "me mostrar",
            "me traga",
            "me trazer",
            "me diga",
            "me dizer",
            "para mim",
            "pra mim",
        )
        if any(marker in normalized for marker in direct_request_markers):
            return False
        how_to_markers = (
            "como faco",
            "como faço",
            "como usar",
            "como funciona",
            "o que e",
            "o que é",
            "para que serve",
            "qual a finalidade",
        )
        if any(re.search(rf"\b{re.escape(marker)}\b", normalized) for marker in how_to_markers):
            return True
        capability_markers = (
            "consegue",
            "vc consegue",
            "voce consegue",
            "você consegue",
            "pode",
            "vc pode",
            "voce pode",
            "você pode",
            "sabe",
            "da para",
            "dá para",
            "e possivel",
            "é possivel",
            "é possível",
        )
        return normalized.startswith(capability_markers)

    def _capability_question_answer(self, normalized_text: str) -> str | None:
        if any(word in normalized_text for word in ("agendar", "agenda", "reuniao", "reunião", "marcar")):
            return (
                "Sim, posso ajudar com agendamento de reunioes. "
                "Como voce fez uma pergunta, nao vou criar nada agora. "
                "Quando quiser iniciar o agendamento, diga algo como: "
                "\"Agende uma reuniao amanha as 10h com Maria sobre demandas atrasadas\". "
                "Se faltarem titulo, data ou participantes, eu vou perguntar; antes de criar, eu mostro a previa e peco confirmacao."
            )
        if any(word in normalized_text for word in ("notificacao", "notificacoes", "notificar", "aviso")):
            return (
                "Sim, posso preparar notificacoes. Envios alteram dados ou disparam comunicacao, entao eu sempre mostro a previa e peco confirmacao antes de enviar."
            )
        if any(word in normalized_text for word in ("rotina", "rotinas")):
            return (
                "Sim, posso consultar rotinas e preparar criacao ou alteracao de rotinas. Consultas respondem direto; criacao, edicao, exclusao ou execucao com impacto exigem confirmacao."
            )
        if any(word in normalized_text for word in ("relatorio", "relatorios", "redmine", "demandas")):
            return (
                "Sim, posso consultar relatorios e preparar execucoes de relatorios Redmine ou IA. Consultas simples podem responder direto; uma nova execucao de relatorio pede confirmacao."
            )
        if any(word in normalized_text for word in ("avaliacao 360", "avaliação 360", "360")):
            return (
                "Sim, posso consultar Avaliacao 360 por funcionario, incluindo ciclo, notas, feedbacks, resumo de IA e alertas quando existirem dados cadastrados."
            )
        return None

    def _knowledge_response(self, command: AssistantCommand, plan: AssistantPlan, user: User | None) -> AssistantResponse | None:
        if self._db_is_mock():
            return None
        if plan.intent != AssistantIntent.UNKNOWN.value and not (plan.domain == "general" and plan.action == "capabilities"):
            return None
        normalized = self._normalize_text(command.text)
        if normalized in {"ajuda", "help", "/help"} or "o que voce consegue fazer" in normalized or "o que voce pode fazer" in normalized:
            return None
        try:
            answer = AssistantKnowledgeService(self.db).answer_question(command.text, user=user)
        except Exception:
            return None
        if not answer:
            return None
        message, data = answer
        return AssistantResponse(
            success=True,
            intent="knowledge_answer",
            domain="general",
            action="knowledge_answer",
            message=message,
            data=data,
        )

    def _db_is_mock(self) -> bool:
        return self.db.__class__.__module__.startswith("unittest.mock")

    def _apply_conversation_context(self, command: AssistantCommand, plan: AssistantPlan, user: User | None) -> AssistantPlan:
        normalized = self._normalize_text(command.text)
        is_contextual = self._looks_contextual(normalized)
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
