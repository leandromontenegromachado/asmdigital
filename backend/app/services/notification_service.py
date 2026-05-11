from __future__ import annotations

import logging
import re
import smtplib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Automation, AutomationRun, Employee, Notification, NotificationRule, NotificationTemplate, Report, ReportRow

logger = logging.getLogger(__name__)

NOTIFICATION_PENDING_APPROVAL = "aguardando_aprovacao"
NOTIFICATION_SENT = "enviado"
NOTIFICATION_ERROR = "erro"
NOTIFICATION_CANCELLED = "cancelado"
NOTIFICATION_PENDING = "pendente"
NOTIFICATION_SIMULATED = "simulado"


class NotificationProvider(ABC):
    channel: str

    @abstractmethod
    def send(self, recipient: str, subject: str | None, message: str, *, simulation: bool = False) -> dict[str, Any]:
        raise NotImplementedError


class EmailNotificationProvider(NotificationProvider):
    channel = "email"

    def send(self, recipient: str, subject: str | None, message: str, *, simulation: bool = False) -> dict[str, Any]:
        if simulation:
            return {"status": "simulated", "recipient": recipient}
        if not settings.smtp_host:
            return {"status": "simulated", "recipient": recipient, "reason": "SMTP_HOST not configured"}

        email = EmailMessage()
        email["Subject"] = subject or "ASMDIGITAL - Notificacao"
        email["From"] = settings.smtp_from
        email["To"] = recipient
        email.set_content(message)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(email)
        return {"status": "sent", "recipient": recipient}


class TeamsNotificationProvider(NotificationProvider):
    channel = "teams"

    def send(self, recipient: str, subject: str | None, message: str, *, simulation: bool = False) -> dict[str, Any]:
        # Placeholder deliberately isolated for future Microsoft Graph integration.
        return {"status": "simulated", "recipient": recipient, "graph_ready": True, "subject": subject}


class InternalNotificationProvider(NotificationProvider):
    channel = "internal"

    def send(self, recipient: str, subject: str | None, message: str, *, simulation: bool = False) -> dict[str, Any]:
        return {"status": "stored", "recipient": recipient, "subject": subject}


PROVIDERS: dict[str, NotificationProvider] = {
    "email": EmailNotificationProvider(),
    "teams": TeamsNotificationProvider(),
    "internal": InternalNotificationProvider(),
}


def render_template(template: str | None, variables: dict[str, Any]) -> str:
    text = template or ""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        value = variables.get(key)
        if value is None:
            return ""
        return str(value)

    return re.sub(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}", replace, text)


def send_notifications_for_automation_run(db: Session, automation: Automation, run: AutomationRun, *, simulation: bool = False) -> list[Notification]:
    rules = (
        db.query(NotificationRule)
        .filter(NotificationRule.automation_id == automation.id, NotificationRule.is_active.is_(True))
        .order_by(NotificationRule.id.asc())
        .all()
    )
    if not rules:
        return []

    items = _structured_items_from_run(db, run)
    created: list[Notification] = []
    for rule in rules:
        if not _condition_matches(rule.send_condition, {"run": run.summary_json or {}, "items": items}):
            continue
        if not items:
            created.append(_create_error_notification(db, automation, run, rule, "Resultado estruturado vazio; nenhum destinatario identificado."))
            continue
        for item in items:
            created.extend(_notifications_for_item(db, automation, run, rule, item, simulation=simulation))

    db.commit()
    for notification in created:
        db.refresh(notification)
    return created


def retry_notification(db: Session, notification: Notification, *, simulation: bool = False) -> Notification:
    if notification.status == NOTIFICATION_CANCELLED:
        return notification
    _dispatch_notification(notification, simulation=simulation)
    db.commit()
    db.refresh(notification)
    return notification


def _notifications_for_item(
    db: Session,
    automation: Automation,
    run: AutomationRun,
    rule: NotificationRule,
    item: dict[str, Any],
    *,
    simulation: bool,
) -> list[Notification]:
    employees = _resolve_recipients(db, rule, item)
    notifications: list[Notification] = []
    if not employees:
        notifications.append(_create_error_notification(db, automation, run, rule, "Funcionario destinatario nao encontrado.", item=item))
        return notifications

    template = rule.template if rule.template and rule.template.is_active else None
    for employee in employees:
        notification = _build_notification(db, automation, run, rule, template, employee, item, simulation=simulation)
        if rule.requires_approval:
            notification.status = NOTIFICATION_PENDING_APPROVAL
        else:
            _dispatch_notification(notification, simulation=simulation)
        db.add(notification)
        notifications.append(notification)
    return notifications


def _build_notification(
    db: Session,
    automation: Automation,
    run: AutomationRun,
    rule: NotificationRule,
    template: NotificationTemplate | None,
    employee: Employee,
    item: dict[str, Any],
    *,
    simulation: bool,
) -> Notification:
    channel = (rule.preferred_channel or employee.canal_preferencial or "email").lower()
    recipient = _recipient_for_channel(employee, channel)
    if not recipient and rule.fallback_channel:
        channel = rule.fallback_channel.lower()
        recipient = _recipient_for_channel(employee, channel)

    variables = _template_variables(automation, run, employee, item)
    subject_template = template.subject if template else 'ASMDIGITAL - Rotina "{{nome_rotina}}"'
    body_template = template.body if template else _default_template()
    subject = render_template(subject_template, variables)
    message = render_template(body_template, variables)

    notification = Notification(
        execution_id=run.id,
        automation_id=automation.id,
        employee_id=employee.id,
        channel=channel,
        recipient=recipient,
        to_ref=recipient,
        subject=subject,
        message=message,
        body=message,
        status=NOTIFICATION_PENDING,
        simulation=simulation,
    )
    if not employee.recebe_notificacao:
        notification.status = NOTIFICATION_CANCELLED
        notification.error = "Funcionario optou por nao receber notificacoes."
    elif not recipient:
        notification.status = NOTIFICATION_ERROR
        notification.error = f"Destinatario sem endereco para canal {channel}."
    return notification


def _dispatch_notification(notification: Notification, *, simulation: bool) -> None:
    if notification.status in {NOTIFICATION_ERROR, NOTIFICATION_CANCELLED, NOTIFICATION_PENDING_APPROVAL}:
        return
    provider = PROVIDERS.get((notification.channel or "").lower())
    notification.attempts = (notification.attempts or 0) + 1
    if not provider:
        notification.status = NOTIFICATION_ERROR
        notification.error = f"Canal nao suportado: {notification.channel}"
        return
    try:
        result = provider.send(notification.recipient or "", notification.subject, notification.message or "", simulation=simulation or notification.simulation)
        if isinstance(result, dict) and result.get("status") == "simulated":
            notification.status = NOTIFICATION_SIMULATED
            notification.error = result.get("reason") or "Envio simulado."
        else:
            notification.status = NOTIFICATION_SENT
            notification.error = None
        now = datetime.now(timezone.utc)
        notification.sent_at = now
        notification.data_envio = now
    except Exception as exc:  # noqa: BLE001
        logger.exception("notification_send_failed", extra={"notification_id": notification.id, "channel": notification.channel})
        notification.status = NOTIFICATION_ERROR
        notification.error = str(exc)


def _create_error_notification(
    db: Session,
    automation: Automation,
    run: AutomationRun,
    rule: NotificationRule,
    error: str,
    item: dict[str, Any] | None = None,
) -> Notification:
    notification = Notification(
        execution_id=run.id,
        automation_id=automation.id,
        channel=rule.preferred_channel or "email",
        recipient=None,
        subject=f"Falha de notificacao - {automation.name}",
        message=str(item or {}),
        body=str(item or {}),
        status=NOTIFICATION_ERROR,
        error=error,
        attempts=0,
        simulation=True,
    )
    db.add(notification)
    return notification


def _resolve_recipients(db: Session, rule: NotificationRule, item: dict[str, Any]) -> list[Employee]:
    recipient_type = (rule.recipient_type or "responsavel").lower()
    if recipient_type == "gestor":
        employee = _employee_from_item(db, item)
        return [employee.manager] if employee and employee.manager else []
    if recipient_type == "funcionario_fixo":
        employee_id = (rule.params_json or {}).get("employee_id")
        employee = db.query(Employee).filter(Employee.id == employee_id).first() if employee_id else None
        return [employee] if employee else []

    employee = _employee_from_item(db, item)
    recipients = [employee] if employee else []
    if rule.notify_manager and employee and employee.manager and _condition_matches(rule.manager_condition, item):
        recipients.append(employee.manager)
    return recipients


def _employee_from_item(db: Session, item: dict[str, Any]) -> Employee | None:
    employee_id = _first_value(item, ["responsavel_id", "employee_id", "funcionario_id", "assigned_to_id"])
    if employee_id:
        try:
            return db.query(Employee).filter(Employee.id == int(employee_id)).first()
        except (TypeError, ValueError):
            pass

    email = _first_value(item, ["responsavel_email", "email", "assigned_to_email"])
    if email:
        employee = db.query(Employee).filter(Employee.email.ilike(str(email))).first()
        if employee:
            return employee

    name = _first_value(item, ["responsavel_nome", "nome_responsavel", "assigned_to", "responsavel"])
    if name:
        return db.query(Employee).filter(Employee.name.ilike(str(name))).first()
    return None


def _recipient_for_channel(employee: Employee, channel: str) -> str | None:
    if channel == "teams":
        return employee.teams_user_id or employee.email
    if channel == "internal":
        return str(employee.id)
    return employee.email


def _structured_items_from_run(db: Session, run: AutomationRun) -> list[dict[str, Any]]:
    summary = run.summary_json or {}
    direct = summary.get("resultados") or summary.get("items_json")
    if isinstance(direct, list):
        return [item for item in direct if isinstance(item, dict)]

    items: list[dict[str, Any]] = []
    for task_result in summary.get("results", []) if isinstance(summary.get("results"), list) else []:
        data = task_result.get("data") if isinstance(task_result, dict) else None
        if isinstance(data, dict):
            if isinstance(data.get("resultados"), list):
                items.extend([item for item in data["resultados"] if isinstance(item, dict)])
            report_id = data.get("report_id")
            if report_id:
                report = db.query(Report).filter(Report.id == int(report_id)).first()
                if report:
                    items.extend(_items_from_report(db, report))
    return items


def _items_from_report(db: Session, report: Report) -> list[dict[str, Any]]:
    rows = db.query(ReportRow).filter(ReportRow.report_id == report.id).order_by(ReportRow.id.asc()).all()
    items: list[dict[str, Any]] = []
    for row in rows:
        raw = row.raw_json if isinstance(row.raw_json, dict) else {}
        item = {
            **raw,
            "cliente": row.cliente,
            "sistema": row.sistema,
            "entrega": row.entrega,
            "source_ref": row.source_ref,
            "source_url": row.source_url,
            "link_relatorio": f"{settings.app_public_url}/reports/redmine-deliveries?report_id={report.id}",
        }
        items.append(item)
    return items


def _template_variables(automation: Automation, run: AutomationRun, employee: Employee, item: dict[str, Any]) -> dict[str, Any]:
    variables = dict(item)
    variables.update(
        {
            "nome": employee.name,
            "nome_responsavel": employee.name,
            "email": employee.email,
            "nome_rotina": automation.name,
            "rotina_id": automation.id,
            "execucao_id": run.id,
            "data_execucao": run.started_at.date().isoformat() if run.started_at else "",
            "link_relatorio": item.get("link_relatorio") or f"{settings.app_public_url}/routines?run_id={run.id}",
            "nome_projeto": item.get("projeto") or item.get("project") or item.get("entrega") or "",
        }
    )
    return variables


def _condition_matches(condition: str | None, context: dict[str, Any]) -> bool:
    if not condition:
        return True
    normalized = condition.strip().lower()
    if normalized in {"always", "sempre", "true"}:
        return True
    if normalized in {"never", "nunca", "false"}:
        return False
    if normalized == "deve_notificar":
        return bool(context.get("deve_notificar") or context.get("run", {}).get("deve_notificar"))
    if normalized == "status_atrasado":
        return str(context.get("status", "")).lower() == "atrasado"
    return True


def _first_value(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _default_template() -> str:
    return (
        "Olá, {{nome_responsavel}}.\n\n"
        'A rotina "{{nome_rotina}}" identificou uma pendência relacionada ao projeto "{{nome_projeto}}".\n\n'
        "Status: {{status}}\n"
        "Dias em atraso: {{dias_atraso}}\n"
        "Data da execução: {{data_execucao}}\n\n"
        "Ação sugerida:\n{{acao_sugerida}}\n\n"
        "Acesse o relatório completo em:\n{{link_relatorio}}\n"
    )
