from __future__ import annotations

from datetime import date, datetime, timezone
import json
import logging
import re
import time
from typing import Any

import httpx
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Automation, AutomationRun, Connector, PromptReportTemplate, Report
from app.services.azure_devops_service import AZURE_CONNECTOR_TYPES, query_snapshot
from app.services.prompt_report_service import run_prompt_report_template
from app.services.report_service import generate_redmine_report

logger = logging.getLogger(__name__)

JOB_PREFIX = "automation:"

AUTOMATION_KEYS = [
    ("redmine_quarterly_report", "Relatorio trimestral Redmine", ["redmine_report"]),
    ("fadpro_ihpe_check", "Verificacao FADPRO/IHPE", []),
    ("azure_epics_overdue", "Azure epicos vencidos", []),
    ("hours_appropriation_watch", "Apropriacao de horas (dedo-duro)", []),
    ("ponto_abono_email", "Email do ponto gerar mensagem de prazo de abono", []),
    ("teams_webhook_notify", "Notificacao via Teams (Webhook, simulacao)", ["webhook_post"]),
]


def build_automation_key(name: str, existing_keys: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not base:
        base = "rotina"
    key = base
    suffix = 2
    while key in existing_keys:
        key = f"{base}_{suffix}"
        suffix += 1
    return key


def ensure_default_automations(db: Session) -> None:
    for key, name, default_tasks in AUTOMATION_KEYS:
        automation = db.query(Automation).filter(Automation.key == key).first()
        if automation:
            continue
        db.add(
            Automation(
                key=key,
                name=name,
                schedule_cron=None,
                is_enabled=True,
                params_json={"simulation": True, "tasks": default_tasks},
            )
        )
    db.commit()


def validate_cron_expression(cron_expression: str | None) -> None:
    if not cron_expression:
        return
    CronTrigger.from_crontab(cron_expression)


def next_run_from_cron(cron_expression: str | None) -> datetime | None:
    if not cron_expression:
        return None
    trigger = CronTrigger.from_crontab(cron_expression, timezone=timezone.utc)
    return trigger.get_next_fire_time(previous_fire_time=None, now=datetime.now(timezone.utc))


def _parse_iso_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _default_month_range() -> tuple[date, date]:
    end_date = date.today()
    return end_date.replace(day=1), end_date


def _parse_kv_args(arg: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for chunk in arg.split(","):
        part = chunk.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        values[key.strip().lower()] = value.strip()
    return values


def _parse_task_line(task: str) -> tuple[str, str]:
    value = task.strip()
    if not value:
        return "", ""
    if ":" not in value:
        return value.lower(), ""
    action, arg = value.split(":", 1)
    return action.strip().lower(), arg.strip()


def _normalize_projects(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r"[|;,]", text)
    return [item.strip() for item in parts if item.strip()]


def _read_task_overrides(arg: str) -> dict[str, Any]:
    if not arg:
        return {}
    if arg.startswith("{") and arg.endswith("}"):
        try:
            payload = json.loads(arg)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            return {}
    return _parse_kv_args(arg)


def _task_result(index: int, task: str, action: str, status: str, message: str, **data: Any) -> dict[str, Any]:
    output = {
        "index": index,
        "task": task,
        "action": action,
        "status": status,
        "message": message,
    }
    if data:
        output["data"] = data
    return output


def _run_redmine_report_task(
    db: Session,
    automation: Automation,
    index: int,
    task_text: str,
    arg: str,
    simulation: bool,
) -> dict[str, Any]:
    params = automation.params_json or {}
    defaults = params.get("redmine_report") if isinstance(params.get("redmine_report"), dict) else {}
    overrides = _read_task_overrides(arg)

    merged: dict[str, Any] = {**defaults, **overrides}
    template_id_raw = merged.get("template_id")
    template_id = int(template_id_raw) if str(template_id_raw or "").isdigit() else None
    if template_id:
        template = db.query(PromptReportTemplate).filter(PromptReportTemplate.id == template_id).first()
        if not template:
            return _task_result(index, task_text, "redmine_report", "failed", f"Template {template_id} nao encontrado")

        if simulation:
            return _task_result(
                index,
                task_text,
                "redmine_report",
                "simulated",
                "Simulacao de execucao via template salvo",
                source_template_id=template_id,
            )

        report, filters = run_prompt_report_template(
            db,
            template,
            trigger=f"automation:{automation.key}",
        )
        return _task_result(
            index,
            task_text,
            "redmine_report",
            "success",
            f"Relatorio #{report.id} gerado via template",
            report_id=report.id,
            report_status=report.status,
            source_template_id=template_id,
            extracted_filters={
                **filters,
                "start_date": str(filters.get("start_date")),
                "end_date": str(filters.get("end_date")),
            },
        )

    report_id_raw = merged.get("report_id")
    report_id = int(report_id_raw) if str(report_id_raw or "").isdigit() else None
    source_report = db.query(Report).filter(Report.id == report_id).first() if report_id else None
    if report_id and not source_report:
        return _task_result(index, task_text, "redmine_report", "failed", f"Relatorio base {report_id} nao encontrado")

    source_params = source_report.params_json if source_report and isinstance(source_report.params_json, dict) else {}

    connector_id_raw = merged.get("connector_id") if merged.get("connector_id") is not None else source_params.get("connector_id")
    connector_id = int(connector_id_raw) if str(connector_id_raw or "").isdigit() else None
    project_ids = _normalize_projects(merged.get("project_ids") if merged.get("project_ids") is not None else source_params.get("project_ids"))

    start_date = _parse_iso_date(merged.get("start_date") if merged.get("start_date") is not None else source_params.get("start_date"))
    end_date = _parse_iso_date(merged.get("end_date") if merged.get("end_date") is not None else source_params.get("end_date"))
    if start_date is None or end_date is None:
        start_date, end_date = _default_month_range()

    status_id = str(merged.get("status_id")).strip() if merged.get("status_id") is not None else (
        str(source_params.get("status_id")).strip() if source_params.get("status_id") is not None else None
    )
    query_id = str(merged.get("query_id")).strip() if merged.get("query_id") is not None else (
        str(source_params.get("query_id")).strip() if source_params.get("query_id") is not None else None
    )
    if status_id == "":
        status_id = None
    if query_id == "":
        query_id = None

    if connector_id is None:
        return _task_result(index, task_text, "redmine_report", "failed", "connector_id obrigatorio")

    if simulation:
        return _task_result(
            index,
            task_text,
            "redmine_report",
            "simulated",
            "Simulacao de geracao de relatorio",
            connector_id=connector_id,
            project_ids=project_ids,
            start_date=str(start_date),
            end_date=str(end_date),
            status_id=status_id,
            query_id=query_id,
            source_report_id=report_id,
        )

    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        return _task_result(index, task_text, "redmine_report", "failed", f"Connector {connector_id} nao encontrado")

    report = generate_redmine_report(
        db=db,
        connector=connector,
        project_ids=project_ids,
        start_date=start_date,
        end_date=end_date,
        status_id=status_id,
        query_id=query_id,
    )

    return _task_result(
        index,
        task_text,
        "redmine_report",
        "success",
        f"Relatorio #{report.id} gerado",
        report_id=report.id,
        report_status=report.status,
        records=(report.params_json or {}).get("records", 0),
        source_report_id=report_id,
    )


def _run_prompt_report_task(
    db: Session,
    automation: Automation,
    index: int,
    task_text: str,
    arg: str,
    simulation: bool,
) -> dict[str, Any]:
    params = automation.params_json or {}
    defaults = params.get("prompt_report") if isinstance(params.get("prompt_report"), dict) else {}
    overrides = _read_task_overrides(arg)

    template_id_raw = overrides.get("template_id") or (arg if arg.isdigit() else None) or defaults.get("template_id")
    template_id = int(template_id_raw) if str(template_id_raw or "").isdigit() else None
    prompt_override = overrides.get("prompt_override") or defaults.get("prompt_override")

    if template_id is None:
        return _task_result(index, task_text, "prompt_report", "failed", "template_id obrigatorio")

    if simulation:
        return _task_result(
            index,
            task_text,
            "prompt_report",
            "simulated",
            "Simulacao de prompt report",
            template_id=template_id,
        )

    template = db.query(PromptReportTemplate).filter(PromptReportTemplate.id == template_id).first()
    if not template:
        return _task_result(index, task_text, "prompt_report", "failed", f"Template {template_id} nao encontrado")

    report, filters = run_prompt_report_template(
        db,
        template,
        prompt_override=str(prompt_override) if prompt_override is not None else None,
        trigger=f"automation:{automation.key}",
    )

    return _task_result(
        index,
        task_text,
        "prompt_report",
        "success",
        f"Prompt report #{report.id} executado",
        template_id=template_id,
        report_id=report.id,
        report_status=report.status,
        extracted_filters={
            **filters,
            "start_date": str(filters.get("start_date")),
            "end_date": str(filters.get("end_date")),
        },
    )


def _run_webhook_task(
    automation: Automation,
    index: int,
    task_text: str,
    arg: str,
    simulation: bool,
) -> dict[str, Any]:
    params = automation.params_json or {}
    defaults = params.get("webhook") if isinstance(params.get("webhook"), dict) else {}
    overrides = _read_task_overrides(arg)

    url = str(overrides.get("url") or defaults.get("url") or "").strip()
    message = str(overrides.get("message") or defaults.get("message") or "Automacao executada").strip()

    if not url:
        return _task_result(index, task_text, "webhook_post", "failed", "url do webhook obrigatoria")

    payload = {
        "automation_id": automation.id,
        "automation_key": automation.key,
        "automation_name": automation.name,
        "task": task_text,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if simulation:
        return _task_result(index, task_text, "webhook_post", "simulated", "Simulacao de envio de webhook", url=url)

    response = httpx.post(url, json=payload, timeout=20)
    response.raise_for_status()

    return _task_result(
        index,
        task_text,
        "webhook_post",
        "success",
        f"Webhook enviado ({response.status_code})",
        status_code=response.status_code,
        url=url,
    )


def _run_sleep_task(index: int, task_text: str, arg: str, simulation: bool) -> dict[str, Any]:
    seconds = 1
    if arg:
        try:
            seconds = max(0, min(int(float(arg)), 60))
        except ValueError:
            seconds = 1

    if simulation:
        return _task_result(index, task_text, "sleep", "simulated", f"Simulacao de espera de {seconds}s")

    time.sleep(seconds)
    return _task_result(index, task_text, "sleep", "success", f"Espera de {seconds}s concluida")


def _run_azure_snapshot_task(
    db: Session,
    automation: Automation,
    index: int,
    task_text: str,
    arg: str,
    simulation: bool,
) -> dict[str, Any]:
    params = automation.params_json or {}
    defaults = params.get("azure_devops") if isinstance(params.get("azure_devops"), dict) else {}
    overrides = _read_task_overrides(arg)
    merged: dict[str, Any] = {**defaults, **overrides}

    connector_id_raw = merged.get("connector_id")
    connector_id = int(connector_id_raw) if str(connector_id_raw or "").isdigit() else None
    project = str(merged.get("project") or "").strip() or None
    team = str(merged.get("team") or "").strip() or None
    area_path = str(merged.get("area_path") or "").strip() or None
    iteration_path = str(merged.get("iteration_path") or "").strip() or None
    top_raw = merged.get("top")
    top = int(top_raw) if str(top_raw or "").isdigit() else 200
    top = max(1, min(top, 1000))

    if connector_id is None:
        return _task_result(index, task_text, "azure_devops_board", "failed", "connector_id obrigatorio")

    if simulation:
        return _task_result(
            index,
            task_text,
            "azure_devops_board",
            "simulated",
            "Simulacao de leitura de quadro Azure DevOps",
            connector_id=connector_id,
            project=project,
            team=team,
            area_path=area_path,
            iteration_path=iteration_path,
            top=top,
        )

    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        return _task_result(index, task_text, "azure_devops_board", "failed", f"Connector {connector_id} nao encontrado")
    if connector.type not in AZURE_CONNECTOR_TYPES:
        return _task_result(index, task_text, "azure_devops_board", "failed", "Connector nao eh Azure DevOps")

    snapshot = query_snapshot(
        connector,
        project=project,
        team=team,
        area_path=area_path,
        iteration_path=iteration_path,
        top=top,
    )
    totals = snapshot.get("totals", {})
    diagnostics = snapshot.get("diagnostics", {})
    pbi_without_task = diagnostics.get("pbi_without_task", {}) if isinstance(diagnostics, dict) else {}
    tasks_without_hours = diagnostics.get("tasks_without_hours", {}) if isinstance(diagnostics, dict) else {}
    hours = totals.get("hours", {})
    return _task_result(
        index,
        task_text,
        "azure_devops_board",
        "success",
        "Snapshot Azure DevOps coletado",
        connector_id=connector_id,
        total_items=totals.get("total", 0),
        with_epic=totals.get("with_epic", 0),
        without_epic=totals.get("without_epic", 0),
        by_state=totals.get("by_state", {}),
        hours=hours,
        pbi_without_task_total=pbi_without_task.get("total", 0),
        tasks_without_hours_total=tasks_without_hours.get("total", 0),
    )


def _execute_task(db: Session, automation: Automation, index: int, task_text: str, simulation: bool) -> dict[str, Any]:
    action, arg = _parse_task_line(task_text)
    if not action:
        return _task_result(index, task_text, "unknown", "skipped", "Tarefa vazia")

    if action in {"redmine_report", "report_redmine", "report.redmine", "gerar_relatorio", "gerar_relatorio_redmine"}:
        return _run_redmine_report_task(db, automation, index, task_text, arg, simulation)

    if action in {"prompt_report", "prompt_report_run", "prompt.template", "template_prompt"}:
        return _run_prompt_report_task(db, automation, index, task_text, arg, simulation)

    if action in {"webhook_post", "notify_webhook", "teams_webhook"}:
        return _run_webhook_task(automation, index, task_text, arg, simulation)

    if action in {"sleep", "wait", "delay"}:
        return _run_sleep_task(index, task_text, arg, simulation)

    if action in {"azure_devops_board", "azure_board_status", "azure_snapshot", "azure_devops_snapshot"}:
        return _run_azure_snapshot_task(db, automation, index, task_text, arg, simulation)

    return _task_result(index, task_text, action, "failed", "Tipo de tarefa desconhecido")


def run_automation(db: Session, automation: Automation, simulation: bool = True) -> AutomationRun:
    run = AutomationRun(
        automation_id=automation.id,
        status="running",
        summary_json={"simulation": simulation},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    params = automation.params_json or {}
    raw_tasks = params.get("tasks") if isinstance(params.get("tasks"), list) else []
    tasks = [task.strip() for task in raw_tasks if isinstance(task, str) and task.strip()]

    task_results: list[dict[str, Any]] = []
    errors: list[str] = []

    for index, task in enumerate(tasks, start=1):
        try:
            result = _execute_task(db, automation, index, task, simulation)
        except Exception as exc:  # noqa: BLE001
            logger.exception("automation_task_failed", extra={"automation_id": automation.id, "task": task, "error": str(exc)})
            result = _task_result(index, task, "unknown", "failed", f"Erro ao executar tarefa: {exc}")
        task_results.append(result)
        if result["status"] == "failed":
            errors.append(f"[{index}] {result['message']}")

    success_count = len([item for item in task_results if item["status"] in {"success", "simulated"}])
    failed_count = len([item for item in task_results if item["status"] == "failed"])

    if failed_count == 0:
        final_status = "success"
        message = "Execucao concluida" if not simulation else "Execucao simulada concluida"
    elif success_count == 0:
        final_status = "failed"
        message = "Execucao falhou"
    else:
        final_status = "completed_with_errors"
        message = "Execucao concluida com erros"

    if not tasks:
        message = "Execucao concluida sem tarefas"
        final_status = "success"

    summary: dict[str, Any] = {
        "message": message,
        "items": len(tasks),
        "tasks": tasks,
        "results": task_results,
        "totals": {
            "success": success_count,
            "failed": failed_count,
            "total": len(tasks),
        },
    }

    run.status = final_status
    run.summary_json = summary
    run.error_text = "\n".join(errors) if errors else None
    run.finished_at = datetime.now(timezone.utc)
    automation.last_run_at = run.finished_at
    automation.next_run_at = next_run_from_cron(automation.schedule_cron) if automation.is_enabled and automation.schedule_cron else None

    db.commit()
    db.refresh(run)
    return run


def sync_automation_jobs(db: Session, scheduler: BaseScheduler) -> None:
    for job in scheduler.get_jobs():
        if job.id.startswith(JOB_PREFIX):
            scheduler.remove_job(job.id)

    automations = db.query(Automation).order_by(Automation.id.asc()).all()
    now_utc = datetime.now(timezone.utc)

    for automation in automations:
        if not automation.is_enabled or not automation.schedule_cron:
            automation.next_run_at = None
            continue

        try:
            trigger = CronTrigger.from_crontab(automation.schedule_cron, timezone=timezone.utc)
        except ValueError:
            automation.next_run_at = None
            continue

        scheduler.add_job(
            execute_automation_job,
            trigger=trigger,
            id=f"{JOB_PREFIX}{automation.id}",
            args=[automation.id],
            replace_existing=True,
        )
        automation.next_run_at = trigger.get_next_fire_time(previous_fire_time=None, now=now_utc)

    db.commit()


def execute_automation_job(automation_id: int) -> None:
    with SessionLocal() as db:
        automation = db.query(Automation).filter(Automation.id == automation_id).first()
        if not automation or not automation.is_enabled:
            return

        simulation = bool((automation.params_json or {}).get("simulation", True))
        run_automation(db, automation, simulation=simulation)
