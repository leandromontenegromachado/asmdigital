from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AssistantCommand(BaseModel):
    text: str = Field(min_length=1)
    user_id: str | None = None
    user_name: str | None = None
    channel: str = "web"
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssistantResponse(BaseModel):
    success: bool
    message: str
    action: str | None = None
    intent: str | None = None
    domain: str | None = None
    requires_confirmation: bool = False
    confirmation_id: str | None = None
    preview: dict[str, Any] = Field(default_factory=dict)
    missing_params: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class AssistantConfirmationRequest(BaseModel):
    confirmed: bool
    user_id: str | None = None
    channel: str = "web"


class VoiceCommandRequest(BaseModel):
    text: str = Field(min_length=1)
    user_id: str | None = None
    source: str = "voice_shortcut"


class AssistantPlan(BaseModel):
    intent: str = "unknown"
    domain: str = "general"
    action: str = "unknown"
    requires_confirmation: bool = False
    confidence: float = 0.0
    extracted_params: dict[str, Any] = Field(default_factory=dict)
    missing_params: list[str] = Field(default_factory=list)
    summary_for_user: str = "Nao entendi o pedido."
    risk_level: str = "low"
    permission_required: str = "funcionario"


class AssistantHistoryItem(BaseModel):
    id: int
    user_id: str | None = None
    user_name: str | None = None
    channel: str
    text: str
    intent: str | None = None
    domain: str | None = None
    action: str | None = None
    response_message: str | None = None
    success: bool
    raw_payload_json: dict[str, Any] = Field(default_factory=dict)
    created_at: Any

    class Config:
        from_attributes = True
