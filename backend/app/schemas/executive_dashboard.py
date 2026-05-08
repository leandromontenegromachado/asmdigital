from datetime import date, datetime

from pydantic import BaseModel


class ExecutiveDashboardRankItem(BaseModel):
    label: str
    count: int


class ExecutiveDashboardEventItem(BaseModel):
    id: int
    title: str
    event_type: str
    severity: str
    status: str
    source_type: str | None = None
    source_id: str | None = None
    created_at: datetime


class ExecutiveDashboardPendingItem(BaseModel):
    id: int
    title: str
    priority: str
    status: str
    responsible_name: str | None = None
    due_date: date | None = None
    source_type: str | None = None
    source_id: str | None = None
    created_at: datetime


class ExecutiveDashboardSummary(BaseModel):
    total_events_today: int
    new_events: int
    high_events: int
    critical_events: int
    open_pending_items: int
    overdue_pending_items: int
    escalated_pending_items: int
    failed_routines_today: int
    top_projects_by_events: list[ExecutiveDashboardRankItem]
    top_responsibles_by_pending_items: list[ExecutiveDashboardRankItem]
    critical_event_list: list[ExecutiveDashboardEventItem]
    overdue_pending_item_list: list[ExecutiveDashboardPendingItem]
