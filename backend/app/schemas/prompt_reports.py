from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PromptReportParams(BaseModel):
    project_ids: list[str] = Field(default_factory=list)
    status_id: Optional[str] = None
    query_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class PromptReportTemplateCreate(BaseModel):
    name: str
    connector_id: int
    prompt_text: str
    params_json: dict[str, Any] = Field(default_factory=dict)
    schedule_cron: Optional[str] = None
    is_enabled: bool = True


class PromptReportTemplateUpdate(BaseModel):
    name: Optional[str] = None
    connector_id: Optional[int] = None
    prompt_text: Optional[str] = None
    params_json: Optional[dict[str, Any]] = None
    schedule_cron: Optional[str] = None
    is_enabled: Optional[bool] = None


class PromptReportTemplateOut(BaseModel):
    id: int
    name: str
    connector_id: int
    prompt_text: str
    params_json: dict[str, Any]
    schedule_cron: Optional[str] = None
    is_enabled: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromptReportRunRequest(BaseModel):
    prompt_override: Optional[str] = None


class PromptReportRunOut(BaseModel):
    report_id: int
    status: str
    extracted_filters: dict[str, Any]
