from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Automation, Connector, Notification, PromptReportTemplate, Report
from app.schemas.dashboard import (
    DashboardAlert,
    DashboardAutomation,
    DashboardConnector,
    DashboardStatSummary,
    DashboardSummary,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

FINISHED_REPORT_STATUSES = {"completed", "completed_with_errors", "failed", "erro", "error"}


def _provider_for_connector(connector: Connector) -> str:
    value = f"{connector.type or ''} {connector.name or ''}".lower()
    if "azure" in value:
        return "azure"
    if "slack" in value:
        return "slack"
    if "jira" in value:
        return "jira"
    if "service" in value:
        return "servicenow"
    return "aws"


def _type_for_connector(connector: Connector) -> str:
    value = f"{connector.type or ''} {connector.name or ''}".lower()
    if any(token in value for token in ("slack", "teams", "email")):
        return "chat"
    if any(token in value for token in ("jira", "redmine", "azure")):
        return "task"
    if any(token in value for token in ("postgres", "db", "database")):
        return "db"
    return "cloud"


def _alert_type(status: str) -> str:
    normalized = (status or "").lower()
    if normalized in {"erro", "error", "failed", "falha"}:
        return "critical"
    if normalized in {"aguardando_aprovacao", "pending", "pendente"}:
        return "warning"
    return "success"


def _alert_tag(status: str) -> str:
    normalized = (status or "").lower()
    if normalized in {"erro", "error", "failed", "falha"}:
        return "Erro"
    if normalized in {"aguardando_aprovacao"}:
        return "Aprovação"
    if normalized in {"pending", "pendente"}:
        return "Pendente"
    return "Enviado"


def _automation_subtitle(params: dict | None, kind: str) -> str:
    params = params or {}
    if kind == "prompt_report":
        project_ids = params.get("project_ids") or params.get("projects") or params.get("projetos")
        if isinstance(project_ids, list) and project_ids:
            return f"Relatório Redmine: {', '.join(str(item) for item in project_ids[:3])}"
        if isinstance(project_ids, str) and project_ids.strip():
            return f"Relatório Redmine: {project_ids}"
        return "Relatório por linguagem natural"

    tasks = params.get("tasks")
    if isinstance(tasks, list) and tasks:
        return ", ".join(str(item) for item in tasks[:2])
    return "Rotina cadastrada"


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    total_connectors = db.query(func.count(Connector.id)).scalar() or 0
    active_connectors = db.query(func.count(Connector.id)).filter(Connector.is_active.is_(True)).scalar() or 0

    notification_timestamp = func.coalesce(Notification.sent_at, Notification.data_envio, Notification.created_at)
    notifications_today = (
        db.query(func.count(Notification.id))
        .filter(notification_timestamp >= today_start)
        .filter(notification_timestamp < today_start + timedelta(days=1))
        .scalar()
        or 0
    )
    notifications_yesterday = (
        db.query(func.count(Notification.id))
        .filter(notification_timestamp >= yesterday_start)
        .filter(notification_timestamp < today_start)
        .scalar()
        or 0
    )

    pending_reports = (
        db.query(func.count(Report.id))
        .filter(or_(Report.status.is_(None), ~Report.status.in_(FINISHED_REPORT_STATUSES)))
        .scalar()
        or 0
    )

    enabled_automations = db.query(func.count(Automation.id)).filter(Automation.is_enabled.is_(True)).scalar() or 0
    enabled_prompt_reports = db.query(func.count(PromptReportTemplate.id)).filter(PromptReportTemplate.is_enabled.is_(True)).scalar() or 0

    connectors = [
        DashboardConnector(
            id=str(connector.id),
            name=connector.name,
            status="online" if connector.is_active else "offline",
            type=_type_for_connector(connector),
            provider=_provider_for_connector(connector),
        )
        for connector in db.query(Connector).order_by(Connector.is_active.desc(), Connector.name.asc()).limit(8).all()
    ]

    recent_notifications = db.query(Notification).order_by(Notification.created_at.desc()).limit(5).all()
    recent_alerts = [
        DashboardAlert(
            id=str(notification.id),
            title=notification.subject or f"Notificação #{notification.id}",
            subtitle=notification.error or notification.recipient or notification.to_ref or "Registro de notificação",
            type=_alert_type(notification.status),
            tag=_alert_tag(notification.status),
            created_at=notification.created_at,
        )
        for notification in recent_notifications
    ]

    scheduled_items: list[DashboardAutomation] = []
    automations = (
        db.query(Automation)
        .filter(Automation.is_enabled.is_(True), Automation.next_run_at.isnot(None))
        .order_by(Automation.next_run_at.asc())
        .limit(6)
        .all()
    )
    for automation in automations:
        scheduled_items.append(
            DashboardAutomation(
                id=f"automation-{automation.id}",
                time=automation.next_run_at.strftime("%d/%m %H:%M") if automation.next_run_at else "-",
                title=automation.name,
                subtitle=_automation_subtitle(automation.params_json, "automation"),
                status="upcoming",
                next_run_at=automation.next_run_at,
            )
        )

    prompt_reports = (
        db.query(PromptReportTemplate)
        .filter(PromptReportTemplate.is_enabled.is_(True), PromptReportTemplate.next_run_at.isnot(None))
        .order_by(PromptReportTemplate.next_run_at.asc())
        .limit(6)
        .all()
    )
    for template in prompt_reports:
        scheduled_items.append(
            DashboardAutomation(
                id=f"prompt-report-{template.id}",
                time=template.next_run_at.strftime("%d/%m %H:%M") if template.next_run_at else "-",
                title=template.name,
                subtitle=_automation_subtitle(template.params_json, "prompt_report"),
                status="upcoming",
                next_run_at=template.next_run_at,
            )
        )

    scheduled_items.sort(key=lambda item: item.next_run_at or now + timedelta(days=365))
    upcoming_automations = scheduled_items[:5]
    for index, item in enumerate(upcoming_automations):
        item.is_next = index == 0
        if index > 0:
            item.status = "pending"

    return DashboardSummary(
        generated_at=now,
        stats=DashboardStatSummary(
            active_connectors=active_connectors,
            total_connectors=total_connectors,
            notifications_today=notifications_today,
            notifications_yesterday=notifications_yesterday,
            pending_reports=pending_reports,
            active_automations=enabled_automations + enabled_prompt_reports,
        ),
        connectors=connectors,
        recent_alerts=recent_alerts,
        upcoming_automations=upcoming_automations,
    )
