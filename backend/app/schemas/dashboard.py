from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DashboardStatSummary(BaseModel):
    active_connectors: int
    total_connectors: int
    notifications_today: int
    notifications_yesterday: int
    pending_reports: int
    active_automations: int


class DashboardConnector(BaseModel):
    id: str
    name: str
    status: str
    type: str
    provider: str


class DashboardAlert(BaseModel):
    id: str
    title: str
    subtitle: str
    type: str
    tag: str
    created_at: Optional[datetime] = None


class DashboardAutomation(BaseModel):
    id: str
    time: str
    title: str
    subtitle: str
    status: str
    is_next: bool = False
    next_run_at: Optional[datetime] = None


class DashboardSummary(BaseModel):
    generated_at: datetime
    stats: DashboardStatSummary
    connectors: list[DashboardConnector]
    recent_alerts: list[DashboardAlert]
    upcoming_automations: list[DashboardAutomation]
