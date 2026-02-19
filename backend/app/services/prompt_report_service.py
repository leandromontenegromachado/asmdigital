from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Connector, PromptReportTemplate, Report
from app.services.report_service import generate_redmine_report

logger = logging.getLogger(__name__)

JOB_PREFIX = "prompt_report_template:"


def _parse_date_token(token: str) -> date | None:
    token = token.strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(token, pattern).date()
        except ValueError:
            continue
    return None


def _project_ids_from_text(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def _default_date_range() -> tuple[date, date]:
    end_date = date.today()
    return end_date.replace(day=1), end_date


def _parse_prompt_filters(prompt: str, defaults: dict[str, Any]) -> dict[str, Any]:
    output = {
        "project_ids": [str(item).strip().lower() for item in defaults.get("project_ids", []) if str(item).strip()],
        "status_id": defaults.get("status_id"),
        "query_id": str(defaults.get("query_id")) if defaults.get("query_id") is not None else None,
        "start_date": _parse_date_token(str(defaults["start_date"])) if defaults.get("start_date") else None,
        "end_date": _parse_date_token(str(defaults["end_date"])) if defaults.get("end_date") else None,
    }

    lowered = prompt.lower()

    query_match = re.search(r"query(?:_id)?\s*[:=]?\s*(\d+)", prompt, flags=re.IGNORECASE)
    if query_match:
        output["query_id"] = query_match.group(1)

    project_match = re.search(r"projetos?\s*[:=]\s*([a-zA-Z0-9_,\-\s]+)", prompt, flags=re.IGNORECASE)
    if project_match:
        output["project_ids"] = _project_ids_from_text(project_match.group(1))

    if "fechado" in lowered or "fechados" in lowered:
        output["status_id"] = "closed"
    elif "aberto" in lowered or "abertos" in lowered:
        output["status_id"] = "open"
    elif "todos os status" in lowered or "qualquer status" in lowered:
        output["status_id"] = None

    last_days_match = re.search(r"ultim[oa]s?\s+(\d+)\s+dias", lowered)
    if last_days_match:
        days = max(1, int(last_days_match.group(1)))
        output["end_date"] = date.today()
        output["start_date"] = output["end_date"] - timedelta(days=days - 1)
    elif "este mes" in lowered or "mês atual" in lowered or "mes atual" in lowered:
        output["start_date"], output["end_date"] = _default_date_range()
    else:
        range_match = re.search(
            r"(?:de|entre)\s+(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\s+(?:a|e)\s+(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})",
            prompt,
            flags=re.IGNORECASE,
        )
        if range_match:
            start_date = _parse_date_token(range_match.group(1))
            end_date = _parse_date_token(range_match.group(2))
            if start_date and end_date:
                output["start_date"] = start_date
                output["end_date"] = end_date

    if output["start_date"] is None or output["end_date"] is None:
        default_start, default_end = _default_date_range()
        output["start_date"] = output["start_date"] or default_start
        output["end_date"] = output["end_date"] or default_end

    if output["start_date"] > output["end_date"]:
        output["start_date"], output["end_date"] = output["end_date"], output["start_date"]

    return output


def validate_cron_expression(cron_expression: str | None) -> None:
    if not cron_expression:
        return
    CronTrigger.from_crontab(cron_expression)


def _next_run_from_cron(cron_expression: str | None) -> datetime | None:
    if not cron_expression:
        return None
    trigger = CronTrigger.from_crontab(cron_expression, timezone=timezone.utc)
    return trigger.get_next_fire_time(previous_fire_time=None, now=datetime.now(timezone.utc))


def run_prompt_report_template(
    db: Session,
    template: PromptReportTemplate,
    prompt_override: str | None = None,
    trigger: str = "manual",
) -> tuple[Report, dict[str, Any]]:
    connector = db.query(Connector).filter(Connector.id == template.connector_id).first()
    if not connector:
        raise ValueError("Connector not found for template")

    effective_prompt = (prompt_override or template.prompt_text or "").strip()
    if not effective_prompt:
        raise ValueError("Prompt is required")

    filters = _parse_prompt_filters(effective_prompt, template.params_json or {})
    if not filters["project_ids"] and not filters["query_id"]:
        raise ValueError("Prompt/defaults must define project_ids or query_id")

    report = generate_redmine_report(
        db=db,
        connector=connector,
        project_ids=filters["project_ids"],
        start_date=filters["start_date"],
        end_date=filters["end_date"],
        status_id=filters["status_id"],
        query_id=filters["query_id"],
    )
    report.params_json = {
        **(report.params_json or {}),
        "template_id": template.id,
        "template_name": template.name,
        "prompt_used": effective_prompt,
        "trigger": trigger,
    }
    db.commit()
    db.refresh(report)

    template.last_run_at = datetime.now(timezone.utc)
    template.next_run_at = _next_run_from_cron(template.schedule_cron) if template.is_enabled else None
    db.commit()
    db.refresh(template)
    return report, filters


def sync_prompt_report_jobs(db: Session, scheduler: BaseScheduler) -> None:
    for job in scheduler.get_jobs():
        if job.id.startswith(JOB_PREFIX):
            scheduler.remove_job(job.id)

    templates = db.query(PromptReportTemplate).order_by(PromptReportTemplate.id.asc()).all()
    now_utc = datetime.now(timezone.utc)
    for template in templates:
        if not template.is_enabled or not template.schedule_cron:
            template.next_run_at = None
            continue

        try:
            trigger = CronTrigger.from_crontab(template.schedule_cron, timezone=timezone.utc)
        except ValueError:
            logger.warning("invalid_prompt_report_cron", extra={"template_id": template.id, "cron": template.schedule_cron})
            template.next_run_at = None
            continue

        scheduler.add_job(
            execute_prompt_report_job,
            trigger=trigger,
            id=f"{JOB_PREFIX}{template.id}",
            args=[template.id],
            replace_existing=True,
        )
        template.next_run_at = trigger.get_next_fire_time(previous_fire_time=None, now=now_utc)

    db.commit()


def execute_prompt_report_job(template_id: int) -> None:
    with SessionLocal() as db:
        template = db.query(PromptReportTemplate).filter(PromptReportTemplate.id == template_id).first()
        if not template or not template.is_enabled:
            return
        try:
            run_prompt_report_template(db, template, trigger="scheduled")
        except Exception as exc:  # noqa: BLE001
            logger.exception("prompt_report_job_failed", extra={"template_id": template_id, "error": str(exc)})
