from __future__ import annotations

from typing import Any

from app.assistant.schemas import AssistantCommand


def build_telegram_command(
    *,
    text: str,
    user_id: str | None,
    user_name: str | None,
    chat_id: str,
    payload: dict[str, Any],
    transcribed_from_voice: bool = False,
) -> AssistantCommand:
    return AssistantCommand(
        text=text,
        user_id=user_id,
        user_name=user_name,
        channel="telegram",
        raw_payload=payload,
        metadata={"chat_id": chat_id, "transcribed_from_voice": transcribed_from_voice},
    )
