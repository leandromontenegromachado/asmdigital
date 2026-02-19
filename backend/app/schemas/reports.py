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
