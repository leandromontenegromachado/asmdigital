from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.assistant.channels.telegram_adapter import build_telegram_command
from app.assistant.service import AssistantCoreService
from app.models import Employee, User
from app.services.assistant_service import AssistantService
from app.services.telegram_service import download_telegram_file, send_telegram_message, transcribe_voice


def process_telegram_update(payload: dict[str, Any], db: Session) -> dict[str, Any]:
    message = payload.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    if not chat_id:
        return {"ok": True, "ignored": "missing_chat_id"}

    user = db.query(User).filter(User.telegram_chat_id == chat_id, User.is_active.is_(True)).first()
    text = str(message.get("text") or "").strip()
    transcribed_from_voice = False
    if not text and message.get("voice"):
        try:
            file_bytes, file_path = download_telegram_file(message["voice"]["file_id"])
            text = transcribe_voice(file_bytes, file_path, _speech_prompt(db))
            transcribed_from_voice = True
        except Exception:
            reply = "Recebi o audio, mas a transcricao de voz ainda nao esta configurada. Envie o pedido em texto."
            send_telegram_message(chat_id, reply)
            return {"ok": True, "reply": reply}

    if text.startswith("/start"):
        reply = (
            "Sou o Assistente de Gestao do ASM Digital. "
            f"Seu chat_id e {chat_id}. Vincule este chat no sistema antes de executar acoes."
        )
        send_telegram_message(chat_id, reply)
        return {"ok": True, "reply": reply}

    if not user:
        reply = f"Este chat ainda nao esta vinculado a um usuario do ASM Digital. Seu chat_id e {chat_id}."
        send_telegram_message(chat_id, reply)
        return {"ok": True, "reply": reply}

    command = build_telegram_command(
        text=text,
        user_id=str(user.id),
        user_name=user.name,
        chat_id=chat_id,
        payload=payload,
        transcribed_from_voice=transcribed_from_voice,
    )
    core_response = AssistantCoreService(db).process_command(command, user=user)
    action = None
    if core_response.message == "LEGACY_ASSISTANT_FALLBACK" or (not core_response.success and "unknown_intent" in core_response.errors):
        _conversation, reply, action = AssistantService(db).handle_message(
            text=text,
            channel="telegram",
            user=user,
            external_chat_id=chat_id,
            raw_payload=payload,
        )
    else:
        reply = core_response.message
        if core_response.requires_confirmation and core_response.confirmation_id:
            reply = f"{reply}\n\nPara confirmar pelo sistema, use o codigo: {core_response.confirmation_id}"
    if transcribed_from_voice:
        reply = f"Entendi seu audio como:\n\"{text}\"\n\n{reply}"
    send_telegram_message(chat_id, reply)
    return {"ok": True, "action_id": action.id if action else None}


def _speech_prompt(db: Session) -> str:
    employees = (
        db.query(Employee)
        .filter(Employee.active.is_(True))
        .order_by(Employee.name.asc())
        .limit(80)
        .all()
    )
    names = ". ".join(employee.name for employee in employees if employee.name)
    return (
        "Use portugues do Brasil. O usuario fala sobre agendamento de reunioes. "
        "Nomes de funcionarios possiveis: "
        f"{names}"
    )
