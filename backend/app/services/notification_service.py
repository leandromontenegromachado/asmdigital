from __future__ import annotations

import logging
import re
import smtplib
import unicodedata
import ast
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from difflib import SequenceMatcher
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
FUZZY_NAME_MIN_SCORE = 0.88
FUZZY_NAME_MIN_GAP = 0.04


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
    if notification.status == NOTIFICATION_ERROR:
        reprocessed = _reprocess_failed_notification(db, notification, simulation=simulation)
        if reprocessed:
            db.commit()
            db.refresh(notification)
            return notification
        notification.status = NOTIFICATION_PENDING
        notification.error = None
    _dispatch_notification(notification, simulation=simulation)
    db.commit()
    db.refresh(notification)
    return notification


def _reprocess_failed_notification(db: Session, notification: Notification, *, simulation: bool) -> bool:
    if notification.employee_id or notification.recipient:
        return False
    if not notification.automation_id:
        return False

    automation = notification.automation or db.query(Automation).filter(Automation.id == notification.automation_id).first()
    run = notification.execution if notification.execution_id else None
    if not run and notification.execution_id:
        run = db.query(AutomationRun).filter(AutomationRun.id == notification.execution_id).first()
    if not automation:
        return False

    items = _items_from_notification_context(db, notification, run)
    if not items:
        return False

    rules = (
        db.query(NotificationRule)
        .filter(NotificationRule.automation_id == notification.automation_id, NotificationRule.is_active.is_(True))
        .order_by(NotificationRule.id.asc())
        .all()
    )
    for rule in rules:
        for item in items:
            employees = _resolve_recipients(db, rule, item)
            if not employees:
                continue
            template = rule.template if rule.template and rule.template.is_active else None
            rebuilt = _build_notification(db, automation, run, rule, template, employees[0], item, simulation=simulation)
            notification.employee_id = rebuilt.employee_id
            notification.channel = rebuilt.channel
            notification.recipient = rebuilt.recipient
            notification.to_ref = rebuilt.to_ref
            notification.subject = rebuilt.subject
            notification.message = rebuilt.message
            notification.body = rebuilt.body
            notification.status = rebuilt.status
            notification.error = rebuilt.error
            notification.simulation = rebuilt.simulation
            if rule.requires_approval:
                notification.status = NOTIFICATION_PENDING_APPROVAL
            else:
                _dispatch_notification(notification, simulation=simulation)
            return True

    target = next((_recipient_reference_from_item(item) for item in items if _recipient_reference_from_item(item)), None)
    notification.error = f"Funcionario destinatario nao encontrado: {target}." if target else "Funcionario destinatario nao encontrado."
    notification.attempts = (notification.attempts or 0) + 1
    return True


def _items_from_notification_context(db: Session, notification: Notification, run: AutomationRun | None) -> list[dict[str, Any]]:
    item = _item_from_notification(notification)
    if item:
        return [item]
    if run:
        return _structured_items_from_run(db, run)
    return []


def _item_from_notification(notification: Notification) -> dict[str, Any] | None:
    for raw in (notification.message, notification.body):
        if not raw:
            continue
        text = raw.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict):
                return parsed
        except (SyntaxError, ValueError):
            pass
    return None


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
        target = _recipient_reference_from_item(item)
        detail = f": {target}" if target else ""
        notifications.append(
            _create_error_notification(
                db,
                automation,
                run,
                rule,
                f"Funcionario destinatario nao encontrado{detail}. Tipo de destinatario: {rule.recipient_type or 'responsavel'}.",
                item=item,
            )
        )
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
    run: AutomationRun | None,
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
        if employee:
            return [employee]
        logger.warning(
            "fixed_employee_notification_without_employee",
            extra={"rule_id": rule.id, "automation_id": rule.automation_id},
        )
        employee = _employee_from_item(db, item)
        return [employee] if employee else []

    employee = _employee_from_item(db, item)
    recipients = [employee] if employee else []
    if rule.notify_manager and employee and employee.manager and _condition_matches(rule.manager_condition, item):
        recipients.append(employee.manager)
    return recipients


def _employee_from_item(db: Session, item: dict[str, Any]) -> Employee | None:
    employee_id = _first_value(item, ["responsavel_id", "employee_id", "funcionario_id", "assigned_to_id", "assignedToId"])
    if employee_id:
        try:
            return db.query(Employee).filter(Employee.id == int(employee_id)).first()
        except (TypeError, ValueError):
            pass

    email = _first_value(item, ["responsavel_email", "email", "assigned_to_email", "assignedToEmail"])
    if email:
        employee = db.query(Employee).filter(Employee.email.ilike(str(email).strip())).first()
        if employee:
            return employee

    name = _first_value(
        item,
        [
            "responsavel_nome",
            "nome_responsavel",
            "assigned_to",
            "assignedTo",
            "responsavel",
            "atribuido_para",
            "atribuído_para",
            "Atribuido para",
            "Atribuído para",
        ],
    )
    if name:
        employee = _employee_by_name(db, name)
        if employee:
            return employee
    return _employee_by_any_text(db, item)


def _employee_by_name(db: Session, name: Any) -> Employee | None:
    collapsed = _collapse_spaces(name)
    if not collapsed:
        return None

    employee = db.query(Employee).filter(Employee.name.ilike(collapsed)).first()
    if employee:
        return employee

    normalized = _normalize_lookup_text(collapsed)
    employees = db.query(Employee).all()
    for candidate in employees:
        if _normalize_lookup_text(candidate.name) == normalized:
            return candidate

    compact = normalized.replace(" ", "")
    for candidate in employees:
        candidate_normalized = _normalize_lookup_text(candidate.name)
        candidate_compact = candidate_normalized.replace(" ", "")
        if candidate_compact and compact and candidate_compact == compact:
            return candidate

    return _employee_by_fuzzy_name(employees, normalized)


def _employee_by_fuzzy_name(employees: list[Employee], normalized_name: str) -> Employee | None:
    scored: list[tuple[float, Employee]] = []
    for employee in employees:
        candidate_name = _normalize_lookup_text(employee.name)
        score = _name_similarity(normalized_name, candidate_name)
        if score >= FUZZY_NAME_MIN_SCORE:
            scored.append((score, employee))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_employee = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    if best_score - second_score < FUZZY_NAME_MIN_GAP:
        logger.warning(
            "ambiguous_employee_name_match",
            extra={
                "searched_name": normalized_name,
                "best_employee_id": best_employee.id,
                "best_score": best_score,
                "second_score": second_score,
            },
        )
        return None

    logger.info(
        "fuzzy_employee_name_match",
        extra={"searched_name": normalized_name, "employee_id": best_employee.id, "score": best_score},
    )
    return best_employee


def _employee_by_any_text(db: Session, item: dict[str, Any]) -> Employee | None:
    text = _flatten_text(item)
    if not text:
        return None
    normalized_text = _normalize_lookup_text(text)
    scored: list[tuple[float, Employee]] = []
    for employee in db.query(Employee).all():
        employee_name = _normalize_lookup_text(employee.name)
        if not employee_name:
            continue
        if employee_name in normalized_text:
            scored.append((1.0, employee))
            continue
        score = _name_similarity(normalized_text, employee_name)
        if score >= FUZZY_NAME_MIN_SCORE:
            scored.append((score, employee))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_employee = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    if best_score - second_score < FUZZY_NAME_MIN_GAP:
        logger.warning(
            "ambiguous_employee_text_match",
            extra={"employee_id": best_employee.id, "best_score": best_score, "second_score": second_score},
        )
        return None
    logger.info("employee_text_match", extra={"employee_id": best_employee.id, "score": best_score})
    return best_employee


def _name_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    ratio = SequenceMatcher(None, left, right).ratio()
    compact_ratio = SequenceMatcher(None, left.replace(" ", ""), right.replace(" ", "")).ratio()
    token_ratio = _token_similarity(left, right)
    containment_ratio = _token_containment_similarity(left, right)
    return max(ratio, compact_ratio, token_ratio, containment_ratio)


def _token_similarity(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union


def _token_containment_similarity(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    min_token_count = min(len(left_tokens), len(right_tokens))
    if min_token_count < 2:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    return intersection / min_token_count


def _flatten_text(value: Any) -> str:
    parts: list[str] = []

    def visit(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, dict):
            for key, nested_value in item.items():
                parts.append(str(key))
                visit(nested_value)
            return
        if isinstance(item, list):
            for nested_value in item:
                visit(nested_value)
            return
        parts.append(str(item))

    visit(value)
    return " ".join(parts)


def _recipient_reference_from_item(item: dict[str, Any]) -> str | None:
    value = _first_value(
        item,
        [
            "responsavel_nome",
            "nome_responsavel",
            "assigned_to",
            "assignedTo",
            "responsavel",
            "atribuido_para",
            "atribuído_para",
            "Atribuido para",
            "Atribuído para",
            "responsavel_email",
            "email",
            "assigned_to_email",
            "assignedToEmail",
            "responsavel_id",
            "employee_id",
            "funcionario_id",
            "assigned_to_id",
            "assignedToId",
        ],
    )
    return _collapse_spaces(value) or None


def _collapse_spaces(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalize_lookup_text(value: Any) -> str:
    text = _collapse_spaces(value)
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return without_accents.casefold()


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


def _template_variables(automation: Automation, run: AutomationRun | None, employee: Employee, item: dict[str, Any]) -> dict[str, Any]:
    variables = dict(item)
    variables.update(
        {
            "nome": employee.name,
            "nome_responsavel": employee.name,
            "email": employee.email,
            "nome_rotina": automation.name,
            "rotina_id": automation.id,
            "execucao_id": run.id if run else "",
            "data_execucao": run.started_at.date().isoformat() if run and run.started_at else "",
            "link_relatorio": item.get("link_relatorio") or (f"{settings.app_public_url}/routines?run_id={run.id}" if run else settings.app_public_url),
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
