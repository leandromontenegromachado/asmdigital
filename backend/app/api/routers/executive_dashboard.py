from collections import Counter
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import Employee, ManagementEvent, PendingItem, User
from app.schemas.executive_dashboard import (
    ExecutiveDashboardEventItem,
    ExecutiveDashboardPendingItem,
    ExecutiveDashboardRankItem,
    ExecutiveDashboardSummary,
)

router = APIRouter(prefix="/executive-dashboard", tags=["executive-dashboard"])


def _today_bounds() -> tuple[datetime, datetime]:
    tz = ZoneInfo(settings.scheduler_timezone)
    today = datetime.now(tz).date()
    return (
        datetime.combine(today, time.min, tzinfo=tz),
        datetime.combine(today, time.max, tzinfo=tz),
    )


def _project_label(event: ManagementEvent) -> str:
    payload = event.payload_json or {}
    management_payload = payload.get("management_event") if isinstance(payload.get("management_event"), dict) else {}
    filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
    project_ids = filters.get("project_ids")
    if isinstance(project_ids, list) and project_ids:
        return str(project_ids[0])
    for key in ("project_id", "project", "projeto"):
        if payload.get(key):
            return str(payload[key])
        if management_payload.get(key):
            return str(management_payload[key])
    if event.source_id:
        return str(event.source_id)
    return event.source_type or "Sem projeto"


def _event_item(event: ManagementEvent) -> ExecutiveDashboardEventItem:
    return ExecutiveDashboardEventItem(
        id=event.id,
        title=event.title,
        event_type=event.event_type,
        severity=event.severity,
        status=event.status,
        source_type=event.source_type,
        source_id=event.source_id,
        created_at=event.created_at,
    )


def _pending_item(item: PendingItem) -> ExecutiveDashboardPendingItem:
    return ExecutiveDashboardPendingItem(
        id=item.id,
        title=item.title,
        priority=item.priority,
        status=item.status,
        responsible_name=item.responsible.name if item.responsible else None,
        due_date=item.due_date,
        source_type=item.source_type,
        source_id=item.source_id,
        created_at=item.created_at,
    )


@router.get("/summary", response_model=ExecutiveDashboardSummary)
def executive_dashboard_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    start, end = _today_bounds()
    today = date.today()
    open_statuses = ("open", "reopened", "escalated")

    events_today_query = db.query(ManagementEvent).filter(
        ManagementEvent.created_at >= start,
        ManagementEvent.created_at <= end,
    )
    events_today = events_today_query.all()

    new_events = events_today_query.filter(ManagementEvent.status == "pending").count()
    high_events = events_today_query.filter(ManagementEvent.severity == "high").count()
    critical_events_count = events_today_query.filter(ManagementEvent.severity == "critical").count()
    failed_routines_today = events_today_query.filter(ManagementEvent.event_type == "ROUTINE_FAILED").count()

    open_pending_items = db.query(PendingItem).filter(PendingItem.status.in_(open_statuses)).count()
    overdue_query = (
        db.query(PendingItem)
        .filter(PendingItem.status.in_(open_statuses))
        .filter(PendingItem.due_date.isnot(None))
        .filter(PendingItem.due_date < today)
    )
    overdue_pending_items_count = overdue_query.count()
    escalated_pending_items = db.query(PendingItem).filter(PendingItem.status == "escalated").count()

    project_counter = Counter(_project_label(event) for event in events_today)
    top_projects = [
        ExecutiveDashboardRankItem(label=label, count=count)
        for label, count in project_counter.most_common(5)
    ]

    responsible_counts = (
        db.query(Employee.name, func.count(PendingItem.id))
        .join(Employee, PendingItem.responsible_id == Employee.id)
        .filter(PendingItem.status.in_(open_statuses))
        .group_by(Employee.name)
        .order_by(func.count(PendingItem.id).desc())
        .limit(5)
        .all()
    )
    top_responsibles = [
        ExecutiveDashboardRankItem(label=name or "Sem responsável", count=count)
        for name, count in responsible_counts
    ]

    critical_events = (
        db.query(ManagementEvent)
        .filter(or_(ManagementEvent.severity == "critical", ManagementEvent.severity == "high"))
        .order_by(ManagementEvent.created_at.desc())
        .limit(10)
        .all()
    )

    overdue_pending_items = overdue_query.order_by(PendingItem.due_date.asc(), PendingItem.created_at.desc()).limit(10).all()

    return ExecutiveDashboardSummary(
        total_events_today=len(events_today),
        new_events=new_events,
        high_events=high_events,
        critical_events=critical_events_count,
        open_pending_items=open_pending_items,
        overdue_pending_items=overdue_pending_items_count,
        escalated_pending_items=escalated_pending_items,
        failed_routines_today=failed_routines_today,
        top_projects_by_events=top_projects,
        top_responsibles_by_pending_items=top_responsibles,
        critical_event_list=[_event_item(event) for event in critical_events],
        overdue_pending_item_list=[_pending_item(item) for item in overdue_pending_items],
    )
