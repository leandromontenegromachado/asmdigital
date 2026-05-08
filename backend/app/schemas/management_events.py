from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ManagementEventBase(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    event_type: str = Field(min_length=2, max_length=80)
    source_type: str | None = Field(default=None, max_length=80)
    source_id: str | None = Field(default=None, max_length=120)
    status: str = "pending"
    severity: str = "medium"
    responsible_id: int | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)


class ManagementEventCreate(ManagementEventBase):
    pass


class ManagementEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    event_type: str | None = Field(default=None, min_length=2, max_length=80)
    source_type: str | None = Field(default=None, max_length=80)
    source_id: str | None = Field(default=None, max_length=120)
    status: str | None = None
    severity: str | None = None
    responsible_id: int | None = None
    payload_json: dict[str, Any] | None = None
    resolution_note: str | None = None


class ManagementEventAction(BaseModel):
    note: str | None = None


class ManagementEventOut(ManagementEventBase):
    id: int
    created_by: int | None = None
    responsible_name: str | None = None
    created_by_name: str | None = None
    processed_at: datetime | None = None
    ignored_at: datetime | None = None
    resolution_note: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ManagementEventSummary(BaseModel):
    total: int
    pending: int
    processed: int
    ignored: int
    by_severity: dict[str, int]
    by_event_type: dict[str, int]
