from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AssistantMessageRequest(BaseModel):
    text: str = Field(min_length=1)
    channel: str = "internal"


class AssistantActionOut(BaseModel):
    id: int
    action_type: str
    status: str
    payload_json: dict[str, Any]
    result_json: dict[str, Any]
    created_at: datetime
    confirmed_at: datetime | None = None

    class Config:
        from_attributes = True


class AssistantMessageResponse(BaseModel):
    conversation_id: int
    reply: str
    action: AssistantActionOut | None = None


class TelegramBindRequest(BaseModel):
    chat_id: str = Field(min_length=1)
    username: str | None = None


class AssistantActionResult(BaseModel):
    id: int
    status: str
    result_json: dict[str, Any]
