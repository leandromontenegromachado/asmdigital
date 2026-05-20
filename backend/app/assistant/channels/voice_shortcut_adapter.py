from __future__ import annotations

from app.assistant.schemas import AssistantCommand, VoiceCommandRequest


def build_voice_shortcut_command(payload: VoiceCommandRequest) -> AssistantCommand:
    return AssistantCommand(
        text=payload.text,
        user_id=payload.user_id,
        channel="voice_shortcut",
        metadata={"source": payload.source},
    )
