from datetime import datetime, date
from typing import Any, Optional

from pydantic import BaseModel


class ReportGenerateRequest(BaseModel):
    connector_id: int
    project_ids: list[str]
    start_date: date
    end_date: date
    status_id: Optional[str] = None
    query_id: Optional[str] = None


class ReportOut(BaseModel):
    id: int
    type: str
    params_json: dict[str, Any]
    generated_at: datetime
    status: str
    file_path: Optional[str] = None

    class Config:
        from_attributes = True


class ReportRowOut(BaseModel):
    id: int
    cliente: Optional[str] = None
    sistema: Optional[str] = None
    entrega: Optional[str] = None
    source_ref: Optional[str] = None
    source_url: Optional[str] = None
    raw_json: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReportDetail(BaseModel):
    report: ReportOut
    rows: list[ReportRowOut]
    total: int
    page: int
    page_size: int
    query: Optional[str] = None


class ReportNotificationRequest(BaseModel):
    row_ids: list[int] | None = None
    template_id: int | None = None
    channel: str | None = None
    subject: str | None = None
    message: str | None = None
    requires_approval: bool = False
    notify_manager: bool = False
    simulation: bool = False


class ReportNotificationItemOut(BaseModel):
    id: int
    row_id: int | None = None
    employee_name: str | None = None
    recipient: str | None = None
    status: str
    error: str | None = None


class ReportNotificationResponse(BaseModel):
    report_id: int
    total: int
    sent: int
    simulated: int
    errors: int
    pending_approval: int
    notifications: list[ReportNotificationItemOut]
