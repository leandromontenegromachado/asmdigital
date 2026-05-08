from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ManagementEventRuleBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    is_active: bool = True
    condition_json: dict[str, Any] = Field(default_factory=dict)
    action_json: dict[str, Any] = Field(default_factory=dict)
    priority: int = 100


class ManagementEventRuleCreate(ManagementEventRuleBase):
    pass


class ManagementEventRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    is_active: bool | None = None
    condition_json: dict[str, Any] | None = None
    action_json: dict[str, Any] | None = None
    priority: int | None = None


class ManagementEventRuleOut(ManagementEventRuleBase):
    id: int
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ManagementEventActionOut(BaseModel):
    id: int
    rule_id: int
    management_event_id: int
    pending_item_id: int | None = None
    action_type: str
    status: str
    message: str | None = None
    action_json: dict[str, Any]
    result_json: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class ManagementEventRuleApplyResult(BaseModel):
    event_id: int
    matched_rules: int
    actions_executed: list[ManagementEventActionOut]
