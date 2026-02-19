from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


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
