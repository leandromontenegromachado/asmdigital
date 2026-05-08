from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.adapters.redmine import RedmineAdapter
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
    projects = []
    for item in value.split(","):
        project = item.strip().strip("{} ").lower()
        if _is_placeholder_project(project):
            continue
        projects.append(project)
    return projects


def _normalize_project_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item).strip().lower()
        for item in value
        if str(item).strip() and not _is_placeholder_project(str(item))
    ]


def _is_placeholder_project(project_id: str) -> bool:
    normalized = project_id.strip().strip("{} ").lower()
    return (
        not normalized
        or normalized in {
            "opcional",
            "optional",
            "projetomodelo",
            "projeto-modelo",
            "projectmodel",
            "project-model",
            "padrao_do_conector",
            "padrao-do-conector",
        }
        or "projeto" in normalized
        or re.fullmatch(r"projeto\d*", normalized) is not None
        or re.fullmatch(r"project\d*", normalized) is not None
    )


def _default_project_ids(connector: Connector) -> list[str]:
    return _normalize_project_ids((connector.config_json or {}).get("project_ids", []))


def _should_use_saved_query(prompt: str) -> bool:
    lowered = prompt.lower()
    return "consulta salva" in lowered or "query salva" in lowered or "queries salvas" in lowered


def _prompt_columns(prompt: str) -> list[dict[str, str]]:
    lowered = prompt.lower()
    candidates = [
        ("subject", "Titulo", ("titulo", "título", "assunto", "demanda")),
        ("assigned_to", "Atribuido para", ("atribuido", "atribuído", "responsavel", "responsável")),
        ("due_date", "Data prevista", ("data prevista", "prevista", "vencimento")),
        ("days_overdue", "Dias em atraso", ("dias em atraso", "dias atraso", "dias vencido", "dias vencidos")),
        ("updated_on", "Alterado em", ("alterado", "atualizado", "modificado")),
        ("status", "Status", ("status", "situacao", "situação")),
        ("priority", "Prioridade", ("prioridade",)),
        ("tracker", "Tipo", ("tipo", "tracker")),
        ("author", "Autor", ("autor", "solicitante")),
        ("done_ratio", "% concluido", ("concluido", "concluído", "percentual", "%")),
    ]
    matched_columns: list[dict[str, str]] = []
    for key, label, terms in candidates:
        if any(term in lowered for term in terms):
            matched_columns.append({"key": key, "label": label})

    concrete_fields = [item for item in matched_columns if item["key"] != "subject"]
    has_explicit_column_request = any(
        term in lowered
        for term in (
            "campos",
            "coluna",
            "colunas",
            "deve ter",
            "deverá ter",
            "devera ter",
            "adicionar",
            "acrescentar",
        )
    )
    if not has_explicit_column_request and not concrete_fields:
        return []

    columns: list[dict[str, str]] = [{"key": "source_ref", "label": "ID"}]
    columns.extend(matched_columns)
    if not any(item["key"] == "subject" for item in columns):
        columns.append({"key": "subject", "label": "Titulo"})
    return columns


def _score_query_name(prompt: str, query: dict[str, Any]) -> int:
    name = str(query.get("name", "")).lower()
    prompt_words = {word for word in re.findall(r"[a-zA-Z0-9_À-ÿ-]{4,}", prompt.lower())}
    return sum(1 for word in prompt_words if word in name)


def _select_saved_query(connector: Connector, project_ids: list[str], prompt: str) -> str | None:
    base_url = (connector.config_json or {}).get("base_url")
    api_key = (connector.config_json or {}).get("api_key")
    if not base_url or not api_key:
        return None

    adapter = RedmineAdapter(base_url=base_url, api_key=api_key)
    candidates: list[dict[str, Any]] = []
    projects = project_ids or _default_project_ids(connector) or [None]
    for project_id in projects:
        try:
            candidates.extend(adapter.fetch_queries(project_id=project_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed_to_load_saved_queries", extra={"project_id": project_id, "error": str(exc)})

    if not candidates:
        return None
    candidates.sort(key=lambda query: _score_query_name(prompt, query), reverse=True)
    if _score_query_name(prompt, candidates[0]) == 0:
        return None
    query_id = candidates[0].get("id")
    return str(query_id) if query_id is not None else None


def _default_date_range() -> tuple[date, date]:
    end_date = date.today()
    return end_date.replace(day=1), end_date


def _parse_prompt_filters(prompt: str, defaults: dict[str, Any]) -> dict[str, Any]:
    output = {
        "project_ids": _normalize_project_ids(defaults.get("project_ids", [])),
        "status_id": defaults.get("status_id"),
        "query_id": str(defaults.get("query_id")) if defaults.get("query_id") is not None else None,
        "start_date": _parse_date_token(str(defaults["start_date"])) if defaults.get("start_date") else None,
        "end_date": _parse_date_token(str(defaults["end_date"])) if defaults.get("end_date") else None,
        "prompt_options": {},
    }

    lowered = prompt.lower()

    query_match = re.search(r"query(?:_id)?\s*[:=]?\s*(\d+)", prompt, flags=re.IGNORECASE)
    if query_match:
        output["query_id"] = query_match.group(1)
    elif re.search(r"query(?:_id)?\s*[:=-]?\s*(opcional|optional|nenhuma?|sem\s+query|-)", lowered):
        output["query_id"] = None

    project_match = re.search(r"projetos?\s*[:=]\s*([^\r\n]+)", prompt, flags=re.IGNORECASE)
    if project_match:
        parsed_projects = _project_ids_from_text(project_match.group(1))
        if parsed_projects:
            output["project_ids"] = parsed_projects

    if "fechado" in lowered or "fechados" in lowered:
        output["status_id"] = "closed"
    elif "aberto" in lowered or "abertos" in lowered or "em execu" in lowered or "em andamento" in lowered:
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

    if "atras" in lowered or "data prevista menor" in lowered or "vencid" in lowered:
        output["prompt_options"] = {
            **output["prompt_options"],
            "overdue_only": True,
            "sort_overdue_first": True,
        }

    output["prompt_options"] = {
        **output["prompt_options"],
        "columns": _prompt_columns(prompt),
    }

    return output


def validate_cron_expression(cron_expression: str | None) -> None:
    if not cron_expression:
        return
    CronTrigger.from_crontab(_normalize_crontab_weekdays(cron_expression))


def _next_run_from_cron(cron_expression: str | None) -> datetime | None:
    if not cron_expression:
        return None
    schedule_timezone = ZoneInfo(settings.scheduler_timezone)
    trigger = CronTrigger.from_crontab(_normalize_crontab_weekdays(cron_expression), timezone=schedule_timezone)
    return trigger.get_next_fire_time(previous_fire_time=None, now=datetime.now(schedule_timezone))


def _schedule_timezone() -> ZoneInfo:
    return ZoneInfo(settings.scheduler_timezone)


def _parse_once_schedule(template: PromptReportTemplate) -> datetime | None:
    params = template.params_json or {}
    if params.get("schedule_mode") != "once":
        return None
    value = params.get("schedule_once_at")
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        run_at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    schedule_timezone = _schedule_timezone()
    if run_at.tzinfo is None:
        return run_at.replace(tzinfo=schedule_timezone)
    return run_at.astimezone(schedule_timezone)


def _next_run_for_template(template: PromptReportTemplate, now: datetime | None = None) -> datetime | None:
    if not template.is_enabled:
        return None
    schedule_timezone = _schedule_timezone()
    current = now or datetime.now(schedule_timezone)
    once_run_at = _parse_once_schedule(template)
    if once_run_at:
        return once_run_at if once_run_at > current else None
    return _next_run_from_cron(template.schedule_cron)


_CRON_WEEKDAY_NAMES = {
    "0": "sun",
    "7": "sun",
    "1": "mon",
    "2": "tue",
    "3": "wed",
    "4": "thu",
    "5": "fri",
    "6": "sat",
}


def _normalize_crontab_weekdays(cron_expression: str) -> str:
    """Use standard crontab weekday numbers before passing the expression to APScheduler."""
    parts = cron_expression.strip().split()
    if len(parts) != 5:
        return cron_expression

    def normalize_token(token: str) -> str:
        if token in ("*", "?"):
            return token
        if "/" in token:
            base, step = token.split("/", 1)
            return f"{normalize_token(base)}/{step}"
        if "-" in token:
            start, end = token.split("-", 1)
            return f"{_CRON_WEEKDAY_NAMES.get(start, start)}-{_CRON_WEEKDAY_NAMES.get(end, end)}"
        return _CRON_WEEKDAY_NAMES.get(token, token)

    parts[4] = ",".join(normalize_token(item.strip().lower()) for item in parts[4].split(",") if item.strip())
    return " ".join(parts)


def run_prompt_report_template(
    db: Session,
    template: PromptReportTemplate,
    prompt_override: str | None = None,
    trigger: str = "manual",
) -> tuple[Report, dict[str, Any]]:
    connector = db.query(Connector).filter(Connector.id == template.connector_id).first()
    if not connector:
        raise ValueError("Connector not found for template")
    if connector.type != "redmine":
        raise ValueError("O template deve usar um conector do tipo Redmine.")

    effective_prompt = (prompt_override or template.prompt_text or "").strip()
    if not effective_prompt:
        raise ValueError("Prompt is required")

    filters = _parse_prompt_filters(effective_prompt, template.params_json or {})
    if not filters["project_ids"]:
        filters["project_ids"] = _default_project_ids(connector)
    if not filters["query_id"] and _should_use_saved_query(effective_prompt):
        filters["query_id"] = _select_saved_query(connector, filters["project_ids"], effective_prompt)
        if not filters["query_id"]:
            logger.info("saved_query_not_selected_falling_back_to_project_filters", extra={"template_id": template.id})
    if filters["query_id"] and _should_use_saved_query(effective_prompt):
        filters["prompt_options"] = {
            **(filters.get("prompt_options") or {}),
            "saved_query_scope": True,
        }
    if not filters["project_ids"] and not filters["query_id"]:
        raise ValueError(
            "Prompt/defaults must define project_ids or query_id. "
            "Preencha Projetos padrao, Query padrao ou configure project_ids no conector."
        )

    report = generate_redmine_report(
        db=db,
        connector=connector,
        project_ids=filters["project_ids"],
        start_date=filters["start_date"],
        end_date=filters["end_date"],
        status_id=filters["status_id"],
        query_id=filters["query_id"],
        prompt_options=filters.get("prompt_options"),
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
    template.next_run_at = _next_run_for_template(template)
    db.commit()
    db.refresh(template)
    return report, filters


def sync_prompt_report_jobs(db: Session, scheduler: BaseScheduler) -> None:
    for job in scheduler.get_jobs():
        if job.id.startswith(JOB_PREFIX):
            scheduler.remove_job(job.id)

    templates = db.query(PromptReportTemplate).order_by(PromptReportTemplate.id.asc()).all()
    schedule_timezone = _schedule_timezone()
    now = datetime.now(schedule_timezone)
    for template in templates:
        if not template.is_enabled:
            template.next_run_at = None
            continue

        once_run_at = _parse_once_schedule(template)
        if once_run_at:
            if once_run_at <= now:
                template.next_run_at = None
                continue
            scheduler.add_job(
                execute_prompt_report_job,
                trigger=DateTrigger(run_date=once_run_at, timezone=schedule_timezone),
                id=f"{JOB_PREFIX}{template.id}",
                args=[template.id],
                replace_existing=True,
            )
            template.next_run_at = once_run_at
            continue

        if not template.schedule_cron:
            template.next_run_at = None
            continue

        try:
            trigger = CronTrigger.from_crontab(_normalize_crontab_weekdays(template.schedule_cron), timezone=schedule_timezone)
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
        template.next_run_at = trigger.get_next_fire_time(previous_fire_time=None, now=now)

    db.commit()


def execute_prompt_report_job(template_id: int) -> None:
    with SessionLocal() as db:
        template = db.query(PromptReportTemplate).filter(PromptReportTemplate.id == template_id).first()
        if not template or not template.is_enabled:
            return
        try:
            run_prompt_report_template(db, template, trigger="scheduled")
            if (template.params_json or {}).get("schedule_mode") == "once":
                template.is_enabled = False
                template.next_run_at = None
                db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("prompt_report_job_failed", extra={"template_id": template_id, "error": str(exc)})
