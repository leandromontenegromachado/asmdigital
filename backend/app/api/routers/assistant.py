from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.assistant.channels.voice_shortcut_adapter import build_voice_shortcut_command
from app.assistant.schemas import (
    AssistantCommand,
    AssistantConfirmationRequest,
    AssistantHistoryItem,
    AssistantKnowledgeSearchRequest,
    AssistantResponse,
    VoiceCommandRequest,
)
from app.assistant.service import AssistantCoreService
from app.core.config import settings
from app.db.session import get_db
from app.models import AssistantAction, User
from app.schemas.assistant import AssistantActionOut, AssistantActionResult, AssistantMessageRequest, AssistantMessageResponse, TelegramBindRequest
from app.services.assistant_service import AssistantService
from app.services.assistant_telegram_handler import process_telegram_update

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _action_out(action: AssistantAction | None) -> AssistantActionOut | None:
    return AssistantActionOut.model_validate(action) if action else None


@router.post("/messages", response_model=AssistantMessageResponse)
def send_assistant_message(
    payload: AssistantMessageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation, reply, action = AssistantService(db).handle_message(text=payload.text, channel=payload.channel, user=user)
    return AssistantMessageResponse(conversation_id=conversation.id, reply=reply, action=_action_out(action))


@router.post("/commands", response_model=AssistantResponse)
def process_assistant_command(
    payload: AssistantCommand,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    command = payload.model_copy(
        update={
            "user_id": payload.user_id or str(user.id),
            "user_name": payload.user_name or user.name,
        }
    )
    response = AssistantCoreService(db).process_command(command, user=user)
    if response.message == "LEGACY_ASSISTANT_FALLBACK":
        conversation, reply, action = AssistantService(db).handle_message(
            text=command.text,
            channel=command.channel,
            user=user,
            raw_payload=command.raw_payload,
        )
        return AssistantResponse(
            success=True,
            intent="CREATE_MEETING",
            domain="meetings",
            action=action.action_type if action else "legacy_assistant_service",
            message=reply,
            requires_confirmation=bool(action and action.status in {"needs_confirmation", "needs_input"}),
            confirmation_id=f"legacy_action:{action.id}" if action else None,
            preview=action.payload_json if action else {},
            missing_params=(action.payload_json or {}).get("missing_fields", []) if action else [],
            data={"conversation_id": conversation.id, "action_id": action.id if action else None},
        )
    return response


@router.post("/voice-command", response_model=AssistantResponse)
def process_voice_shortcut_command(
    payload: VoiceCommandRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    command = build_voice_shortcut_command(payload).model_copy(
        update={"user_id": payload.user_id or str(user.id), "user_name": user.name}
    )
    return AssistantCoreService(db).process_command(command, user=user)


@router.post("/voice-shortcut", response_model=AssistantResponse)
def process_public_voice_shortcut(
    payload: VoiceCommandRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    expected_token = (settings.assistant_voice_shortcut_token or "").strip()
    if not expected_token:
        raise HTTPException(status_code=503, detail="Voice shortcut token is not configured")
    provided_token = (authorization or "").replace("Bearer ", "", 1).strip()
    if provided_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid voice shortcut token")

    user = None
    if settings.assistant_voice_shortcut_user_email:
        user = (
            db.query(User)
            .filter(User.email == settings.assistant_voice_shortcut_user_email.strip().lower(), User.is_active.is_(True))
            .first()
        )
    command = build_voice_shortcut_command(payload).model_copy(
        update={
            "channel": "voice_shortcut",
            "user_id": payload.user_id or (str(user.id) if user else "voice_shortcut"),
            "user_name": user.name if user else payload.user_id,
        }
    )
    response = AssistantCoreService(db).process_command(command, user=user)
    if response.message == "LEGACY_ASSISTANT_FALLBACK":
        return AssistantResponse(
            success=False,
            intent="CREATE_MEETING",
            domain="meetings",
            action="legacy_assistant_service",
            message="Pedidos de reuniao por atalho de voz ainda precisam ser confirmados no canal autenticado.",
            errors=["confirmation_channel_required"],
        )
    return response


@router.post("/confirmations/{confirmation_id}", response_model=AssistantResponse)
def confirm_assistant_core_action(
    confirmation_id: str,
    payload: AssistantConfirmationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if confirmation_id.startswith("legacy_action:"):
        action_id = confirmation_id.replace("legacy_action:", "").strip()
        if not action_id.isdigit():
            raise HTTPException(status_code=404, detail="Assistant action not found")
        action = db.query(AssistantAction).filter(AssistantAction.id == int(action_id)).first()
        if not action:
            raise HTTPException(status_code=404, detail="Assistant action not found")
        if not payload.confirmed:
            action = AssistantService(db).cancel_action(action)
        else:
            action = AssistantService(db).confirm_action(action)
        return AssistantResponse(
            success=action.status in {"completed", "cancelled", "needs_input"},
            domain="meetings",
            action=action.action_type,
            message="Acao confirmada." if payload.confirmed else "Acao cancelada.",
            data=action.result_json or {},
            errors=[] if action.status != "error" else ["legacy_action_error"],
        )
    return AssistantCoreService(db).confirm(confirmation_id, payload.confirmed, user=user, channel=payload.channel)


@router.get("/history", response_model=list[AssistantHistoryItem])
def list_assistant_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return AssistantCoreService(db).history(user=user, limit=limit)


@router.get("/capabilities")
def list_assistant_capabilities(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return AssistantCoreService(db).capabilities()


@router.post("/knowledge/seed")
def seed_assistant_knowledge(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return AssistantCoreService(db).seed_knowledge()


@router.post("/knowledge/search")
def search_assistant_knowledge(
    payload: AssistantKnowledgeSearchRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return AssistantCoreService(db).search_knowledge(payload.query, limit=payload.limit)


@router.post("/telegram/bind-current")
def bind_current_telegram_chat(
    payload: TelegramBindRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    AssistantService(db).bind_telegram(user, payload.chat_id, payload.username)
    return {"status": "linked", "chat_id": payload.chat_id}


@router.get("/actions", response_model=list[AssistantActionOut])
def list_assistant_actions(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return db.query(AssistantAction).order_by(AssistantAction.created_at.desc()).limit(100).all()


@router.post("/actions/{action_id}/confirm", response_model=AssistantActionResult)
def confirm_assistant_action(
    action_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    action = db.query(AssistantAction).filter(AssistantAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Assistant action not found")
    if action.user_id and action.user_id != user.id and user.role not in {"admin", "gerente"}:
        raise HTTPException(status_code=403, detail="Action belongs to another user")
    action = AssistantService(db).confirm_action(action)
    return AssistantActionResult(id=action.id, status=action.status, result_json=action.result_json or {})


@router.post("/actions/{action_id}/cancel", response_model=AssistantActionResult)
def cancel_assistant_action(
    action_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    action = db.query(AssistantAction).filter(AssistantAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Assistant action not found")
    if action.user_id and action.user_id != user.id and user.role not in {"admin", "gerente"}:
        raise HTTPException(status_code=403, detail="Action belongs to another user")
    action = AssistantService(db).cancel_action(action)
    return AssistantActionResult(id=action.id, status=action.status, result_json=action.result_json or {})


@router.post("/telegram/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    expected_secret = (settings.telegram_webhook_secret or "").strip()
    if not expected_secret:
        raise HTTPException(status_code=503, detail="Telegram webhook secret is not configured")
    provided_secret = (x_telegram_bot_api_secret_token or "").strip()
    if not secrets.compare_digest(provided_secret, expected_secret):
        raise HTTPException(status_code=403, detail="Invalid Telegram secret")
    payload = await request.json()
    return process_telegram_update(payload, db)
