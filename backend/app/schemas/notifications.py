from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NotificationTemplateBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    variable_automation_id: int | None = None
    channel: str = "email"
    subject: str | None = None
    body: str = Field(min_length=1)
    is_active: bool = True


class NotificationTemplateCreate(NotificationTemplateBase):
    pass


class NotificationTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    variable_automation_id: int | None = None
    channel: str | None = None
    subject: str | None = None
    body: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class NotificationTemplateOut(NotificationTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationRuleBase(BaseModel):
    automation_id: int
    is_active: bool = True
    send_condition: str | None = None
    recipient_type: str = "responsavel"
    preferred_channel: str = "email"
    fallback_channel: str | None = None
    template_id: int | None = None
    requires_approval: bool = False
    notify_manager: bool = False
    manager_condition: str | None = None
    params_json: dict[str, Any] = Field(default_factory=dict)


class NotificationRuleCreate(NotificationRuleBase):
    pass


class NotificationRuleUpdate(BaseModel):
    automation_id: int | None = None
    is_active: bool | None = None
    send_condition: str | None = None
    recipient_type: str | None = None
    preferred_channel: str | None = None
    fallback_channel: str | None = None
    template_id: int | None = None
    requires_approval: bool | None = None
    notify_manager: bool | None = None
    manager_condition: str | None = None
    params_json: dict[str, Any] | None = None


class NotificationRuleOut(NotificationRuleBase):
    id: int
    template_name: str | None = None
    automation_name: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationOut(BaseModel):
    id: int
    execution_id: int | None = None
    automation_id: int | None = None
    automation_name: str | None = None
    employee_id: int | None = None
    employee_name: str | None = None
    channel: str
    recipient: str | None = None
    subject: str | None = None
    message: str | None = None
    status: str
    data_envio: datetime | None = None
    sent_at: datetime | None = None
    error: str | None = None
    attempts: int
    simulation: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationRetryOut(BaseModel):
    id: int
    status: str
    error: str | None = None
    attempts: int
