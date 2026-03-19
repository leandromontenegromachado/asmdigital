from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AutomationOut(BaseModel):
    id: int
    key: str
    name: str
    schedule_cron: Optional[str] = None
    is_enabled: bool
    params_json: dict[str, Any]
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AutomationRunOut(BaseModel):
    id: int
    automation_id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    summary_json: dict[str, Any]
    error_text: Optional[str] = None

    class Config:
        from_attributes = True


class AutomationRunRequest(BaseModel):
    simulation: bool = True


class AutomationUpdate(BaseModel):
    name: Optional[str] = None
    schedule_cron: Optional[str] = None
    is_enabled: Optional[bool] = None
    params_json: Optional[dict[str, Any]] = None


class AutomationCreate(BaseModel):
    name: str
    schedule_cron: Optional[str] = None
    is_enabled: bool = True
    params_json: dict[str, Any] = Field(default_factory=dict)


class AutomationRunWithAutomation(BaseModel):
    id: int
    automation_id: int
    automation_name: str
    automation_key: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    summary_json: dict[str, Any]
    error_text: Optional[str] = None
