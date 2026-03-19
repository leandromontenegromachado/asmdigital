from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, Field


class FalaAiCheckinCreate(BaseModel):
    user_id: int | None = None
    timestamp: datetime | None = None
    tipo: str = "manual"
    origem: str = "web"


class FalaAiCheckinOut(BaseModel):
    id: int
    user_id: int
    tipo: str
    origem: str
    created_at: datetime

    class Config:
        from_attributes = True


class FalaAiReminderCreate(BaseModel):
    mensagem: str = Field(min_length=1, max_length=1000)
    horario: time
    ativo: bool = True


class FalaAiReminderUpdate(BaseModel):
    mensagem: str | None = Field(default=None, min_length=1, max_length=1000)
    horario: time | None = None
    ativo: bool | None = None


class FalaAiReminderOut(BaseModel):
    id: int
    mensagem: str
    horario: time
    ativo: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FalaAiLogOut(BaseModel):
    id: int
    evento: str
    payload: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class FalaAiDailyUserStatus(BaseModel):
    user_id: int
    name: str
    email: str
    last_checkin_at: datetime | None = None


class FalaAiDailyReportOut(BaseModel):
    date: date
    checked_in_users: list[FalaAiDailyUserStatus]
    missing_users: list[FalaAiDailyUserStatus]


class FalaAiWebhookResponse(BaseModel):
    status: str
    detail: str
    checkin_id: int | None = None
    reply_message: str | None = None


class FalaAiBotReplyIn(BaseModel):
    mensagem: str = Field(min_length=1, max_length=1000)


class FalaAiBotReplyOut(BaseModel):
    resposta: str


class FalaAiDispatchConfirmationOut(BaseModel):
    user_id: int
    name: str
    email: str
    confirmation: dict[str, Any] | None = None


class FalaAiDispatchReportOut(BaseModel):
    dispatch_id: str
    reminder_id: int | None = None
    message: str | None = None
    sent_at: str | None = None
    channel_id: str | None = None
    conversation_id: str | None = None
    checked_in_users: list[FalaAiDispatchConfirmationOut]
    missing_users: list[FalaAiDispatchConfirmationOut]


class FalaAiPollHistoryItemOut(BaseModel):
    dispatch_id: str
    reminder_id: int | None = None
    message: str | None = None
    sent_at: str | None = None
    checked_in_total: int
    missing_total: int
