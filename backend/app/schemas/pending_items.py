from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class PendingItemBase(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    status: str = "open"
    priority: str = "medium"
    source_type: str | None = Field(default=None, max_length=80)
    source_id: str | None = Field(default=None, max_length=120)
    management_event_id: int | None = None
    responsible_id: int | None = None
    due_date: date | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)


class PendingItemCreate(PendingItemBase):
    pass


class PendingItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    source_type: str | None = Field(default=None, max_length=80)
    source_id: str | None = Field(default=None, max_length=120)
    management_event_id: int | None = None
    responsible_id: int | None = None
    due_date: date | None = None
    payload_json: dict[str, Any] | None = None
    resolution_note: str | None = None


class PendingItemAction(BaseModel):
    note: str | None = None


class PendingItemEventOut(BaseModel):
    id: int
    pending_item_id: int
    event_type: str
    old_status: str | None = None
    new_status: str | None = None
    note: str | None = None
    actor_id: int | None = None
    actor_name: str | None = None
    payload_json: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class PendingItemOut(PendingItemBase):
    id: int
    created_by: int | None = None
    responsible_name: str | None = None
    created_by_name: str | None = None
    resolved_at: datetime | None = None
    ignored_at: datetime | None = None
    escalated_at: datetime | None = None
    reopened_at: datetime | None = None
    resolution_note: str | None = None
    created_at: datetime
    updated_at: datetime
    events: list[PendingItemEventOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PendingItemSummary(BaseModel):
    total: int
    open: int
    resolved: int
    ignored: int
    escalated: int
    reopened: int
    by_priority: dict[str, int]
    by_source_type: dict[str, int]
