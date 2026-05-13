from __future__ import annotations

import logging
import json
import re
import unicodedata
import hashlib
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any

import httpx
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.adapters.redmine import RedmineAdapter
from app.db.session import SessionLocal
from app.models import Automation, AutomationRun, Connector, PromptReportTemplate, Report
from app.services.ai_model_service import generate_ai_text, resolve_ai_model
from app.services.management_event_service import register_management_event_safe
from app.services.notification_service import send_notifications_for_automation_run
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


PROMPT_COLUMN_CANDIDATES = [
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
    ("cliente", "Cliente", ("cliente",)),
    ("sistema", "Sistema", ("sistema",)),
    ("entrega", "Entrega", ("entrega",)),
]

DEFAULT_REDMINE_COLUMNS = [
    {"key": "source_ref", "label": "ID"},
    {"key": "subject", "label": "Titulo"},
    {"key": "assigned_to", "label": "Atribuido para"},
    {"key": "due_date", "label": "Data prevista"},
    {"key": "updated_on", "label": "Alterado em"},
    {"key": "status", "label": "Status"},
]

PROMPT_FIELD_LABELS = {key: label for key, label, _ in PROMPT_COLUMN_CANDIDATES}
PROMPT_FIELD_LABELS["source_ref"] = "ID"
PROMPT_ALLOWED_FIELDS = set(PROMPT_FIELD_LABELS) | {"created_on"}
PROMPT_ALLOWED_OPERATORS = {
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "contains",
    "not_contains",
    "in",
    "not_in",
    "is_empty",
    "is_not_empty",
}


def _prompt_columns(prompt: str) -> list[dict[str, str]]:
    lowered = prompt.lower()
    excluded_columns = set(_parse_excluded_columns(prompt))
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
    for key, label, terms in PROMPT_COLUMN_CANDIDATES:
        if key not in excluded_columns and any(term in lowered for term in terms):
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
            "incluir",
            "tirar",
            "remover",
            "nao exibir",
            "não exibir",
        )
    )
    if not has_explicit_column_request and not concrete_fields and not excluded_columns:
        return []

    if excluded_columns and not matched_columns:
        return [column for column in DEFAULT_REDMINE_COLUMNS if column["key"] not in excluded_columns]

    columns: list[dict[str, str]] = [{"key": "source_ref", "label": "ID"}]
    columns.extend(matched_columns)
    if "subject" not in excluded_columns and not any(item["key"] == "subject" for item in columns):
        columns.append({"key": "subject", "label": "Titulo"})
    return columns


def _score_query_name(prompt: str, query: dict[str, Any]) -> int:
    name = str(query.get("name", "")).lower()
    prompt_words = {word for word in re.findall(r"[a-zA-Z0-9_À-ÿ-]{4,}", prompt.lower())}
    return sum(1 for word in prompt_words if word in name)


def _normalize_prompt_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _split_prompt_list(value: str) -> list[str]:
    value = re.split(
        r"\s+(?:,|;|\be\b)\s+(?:status(?:es)?|prioridade|tipo|tracker|autor|solicitante|responsavel|responsável|atribuido(?:\s+para)?|atribuído(?:\s+para)?|titulo|título|assunto|demanda|cliente|sistema|entrega)\s+(?:diferente|nao|não|exceto|menos)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    value = re.split(
        r"\s+(?:com|adicionar|acrescentar|colocar|incluir|tirar|remover|excluir|ocultar|nao\s+exibir|não\s+exibir|dias?\s+em\s+atraso|colunas?|campos?|orden|periodo|projetos?|query)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    parts = re.split(r"\s*(?:,|;|/|\bou\b|\be\b)\s*", value, flags=re.IGNORECASE)
    ignored = {"", "status", "de", "do", "da", "dos", "das", "que", "seja", "for", "esteja"}
    return [part.strip(" .:-").strip() for part in parts if part.strip(" .:-").strip().lower() not in ignored]


def _field_from_prompt_label(value: str) -> str | None:
    normalized = _normalize_prompt_text(value).strip()
    aliases = {
        "source_ref": ("id", "numero", "número", "codigo", "código"),
        "subject": ("titulo", "título", "assunto", "demanda"),
        "assigned_to": ("atribuido", "atribuído", "atribuido para", "responsavel", "responsável"),
        "due_date": ("data prevista", "prevista", "vencimento"),
        "days_overdue": ("dias em atraso", "dias atraso", "dias vencido", "dias vencidos"),
        "updated_on": ("alterado", "atualizado", "modificado"),
        "status": ("status", "situacao", "situação"),
        "priority": ("prioridade",),
        "tracker": ("tipo", "tracker"),
        "author": ("autor", "solicitante"),
        "done_ratio": ("concluido", "concluído", "percentual", "%"),
        "cliente": ("cliente",),
        "sistema": ("sistema",),
        "entrega": ("entrega",),
    }
    for field, terms in aliases.items():
        if normalized == field or any(normalized == _normalize_prompt_text(term) for term in terms):
            return field
    for field, _, terms in PROMPT_COLUMN_CANDIDATES:
        if any(_normalize_prompt_text(term) in normalized for term in terms):
            return field
    return None


def _parse_excluded_columns(prompt: str) -> list[str]:
    normalized = _normalize_prompt_text(prompt)
    patterns = [
        r"(?:nao|não)\s+(?:exibir|mostrar|listar)\s+(?:a\s+)?(?:coluna|campo)?s?\s*([^\r\n.]+)",
        r"(?:tirar|remover|excluir|ocultar)\s+(?:a\s+)?(?:coluna|campo)?s?\s*([^\r\n.]+)",
        r"(?:sem)\s+(?:a\s+)?(?:coluna|campo)?s?\s*([^\r\n.]+)",
    ]
    excluded: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
            raw_value = match.group(1).strip()
            for item in _split_prompt_list(raw_value) or [raw_value]:
                field = _field_from_prompt_label(item)
                if field:
                    excluded.append(field)
    return list(dict.fromkeys(excluded))


def _parse_excluded_field_values(prompt: str) -> list[dict[str, Any]]:
    normalized = _normalize_prompt_text(prompt)
    field_pattern = (
        r"status(?:es)?|prioridade|tipo|tracker|autor|solicitante|responsavel|responsável|"
        r"atribuido(?:\s+para)?|atribuído(?:\s+para)?|titulo|título|assunto|demanda|"
        r"cliente|sistema|entrega"
    )
    next_rule = rf"(?=\s+(?:,|;|\be\b)\s+(?:{field_pattern})\s+(?:diferente|nao|não|exceto|menos)|[\r\n.]|$)"
    patterns = [
        rf"(?P<field>{field_pattern})\s+(?:diferente(?:s)?\s+de|nao\s+(?:seja|sejam|for|esteja|estejam)|"
        rf"não\s+(?:seja|sejam|for|esteja|estejam)|exceto|menos)\s+(?P<values>.*?){next_rule}",
        rf"(?:exceto|excluir|exclua|remover|remova|sem)\s+(?P<field>{field_pattern})\s+(?P<values>.*?){next_rule}",
        rf"(?:nao|não)\s+(?:trazer|listar|mostrar|exibir|incluir|retornar)\s+.*?(?P<field>{field_pattern})\s+(?:de|=|:)?\s*(?P<values>.*?){next_rule}",
    ]
    rules: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
            field = _field_from_prompt_label(match.group("field"))
            values = _split_prompt_list(match.group("values"))
            if not field or not values:
                continue
            if field == "subject" and any(_normalize_prompt_text(item) in {"que estao", "que estejam"} for item in values):
                continue
            normalized_values = tuple(dict.fromkeys(_normalize_prompt_text(item) for item in values if item.strip()))
            key = (field, normalized_values)
            if normalized_values and key not in seen:
                seen.add(key)
                rules.append({"field": field, "operator": "neq", "values": list(values)})

    status_line_patterns = [
        r"(?:nao|não)\s+(?:trazer|listar|mostrar|exibir|retornar|incluir)\b[^\r\n.]{0,140}?\bstatus\s+(?:de\s+|do\s+|da\s+|com\s+|=|:)?(?P<values>.*?)(?=\s+(?:e\s+tambem|tambem|com\s+dias|dias?\s+em\s+atraso|periodo|colunas?|campos?)|[\r\n.]|$)",
        r"(?:sem|exceto|excluir|remover)\b[^\r\n.]{0,80}?\bstatus\s+(?:de\s+|do\s+|da\s+|com\s+|=|:)?(?P<values>.*?)(?=\s+(?:e\s+tambem|tambem|com\s+dias|dias?\s+em\s+atraso|periodo|colunas?|campos?)|[\r\n.]|$)",
    ]
    for pattern in status_line_patterns:
        for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
            values = _split_prompt_list(match.group("values"))
            normalized_values = tuple(dict.fromkeys(_normalize_prompt_text(item) for item in values if item.strip()))
            key = ("status", normalized_values)
            if normalized_values and key not in seen:
                seen.add(key)
                rules.append({"field": "status", "operator": "not_in", "values": list(values)})
    return rules


def _parse_prompt_numeric_filters(prompt: str) -> list[dict[str, Any]]:
    normalized = _normalize_prompt_text(prompt)
    filters: list[dict[str, Any]] = []
    max_days_patterns = [
        r"(?:nao|não)\s+(?:trazer|listar|mostrar|exibir|retornar|incluir)\b[^\r\n.]{0,120}?dias?\s+em\s+atraso[^\r\n.]{0,80}?(?:mais\s+de|maior(?:es)?\s+que|acima\s+de)\s*(\d+)",
        r"dias?\s+em\s+atraso\s*(?:<=|menor(?:es)?\s+ou\s+igual(?:is)?\s+a|ate|até)\s*(\d+)",
    ]
    for pattern in max_days_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            filters.append({"field": "days_overdue", "operator": "lte", "values": [match.group(1)]})
            break
    return filters


def _prompt_fingerprint(prompt: str) -> str:
    normalized = re.sub(r"\s+", " ", (prompt or "").strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _cached_prompt_options(defaults: dict[str, Any], prompt: str) -> dict[str, Any] | None:
    cached = defaults.get("last_prompt_interpretation")
    if not isinstance(cached, dict):
        return None
    if cached.get("prompt_hash") != _prompt_fingerprint(prompt):
        return None
    options = cached.get("prompt_options")
    return options if isinstance(options, dict) else None


def _parse_excluded_status_names(prompt: str) -> list[str]:
    normalized = _normalize_prompt_text(prompt)
    patterns = [
        r"status(?:es)?\s+(?:diferente(?:s)?\s+de|nao\s+(?:seja|sejam|for|esteja|estejam))\s+([^\r\n.]+)",
        r"(?:exceto|excluir|exclua|remover|remova)\s+status(?:es)?\s+([^\r\n.]+)",
        r"status(?:es)?\s+(?:exceto|menos)\s+([^\r\n.]+)",
    ]
    excluded: list[str] = []
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            excluded.extend(_split_prompt_list(match.group(1)))

    seen = set()
    result = []
    for item in excluded:
        key = _normalize_prompt_text(item)
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _extract_json_object(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        value = value.strip("`").strip()
        if value.lower().startswith("json"):
            value = value[4:].strip()
    if value.startswith("{") and value.endswith("}"):
        return value
    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end > start:
        return value[start:end + 1]
    return value


def _build_prompt_interpreter_request(prompt: str, defaults: dict[str, Any], connector: Connector | None) -> str:
    connector_projects = _default_project_ids(connector) if connector else []
    fields = {
        "source_ref": "ID da demanda",
        "subject": "titulo/assunto",
        "assigned_to": "responsavel/atribuido para",
        "due_date": "data prevista",
        "days_overdue": "dias em atraso calculado",
        "updated_on": "alterado em",
        "created_on": "criado em",
        "status": "status/situacao",
        "priority": "prioridade",
        "tracker": "tipo/tracker",
        "author": "autor/solicitante",
        "done_ratio": "percentual concluido",
        "cliente": "cliente normalizado",
        "sistema": "sistema normalizado",
        "entrega": "entrega normalizada",
    }
    contract = {
        "project_ids": ["asm-dem"],
        "query_id": None,
        "status_id": "open | closed | null",
        "start_date": "YYYY-MM-DD ou null",
        "end_date": "YYYY-MM-DD ou null",
        "use_saved_query": False,
        "columns": [{"key": "subject", "label": "Titulo"}],
        "filters": [{"field": "status", "operator": "not_in", "values": ["Homologacao"]}],
        "sort": [{"field": "days_overdue", "direction": "desc"}],
        "overdue_only": False,
        "notes": "texto curto opcional",
    }
    return (
        "Interprete o prompt de relatorio Redmine e retorne somente JSON valido.\n"
        "Nao execute consulta e nao invente campos fora da lista permitida.\n"
        "Use datas em ISO YYYY-MM-DD. Para hoje use a data atual informada.\n"
        "Quando o usuario pedir para tirar/remover/nao exibir colunas, retorne columns com a lista final exibida.\n"
        "Quando o usuario pedir regra de nao exibicao de linhas, retorne em filters.\n"
        "Exemplo: 'nao trazer demandas com status de homologada e homologacao' deve virar "
        "{\"field\":\"status\",\"operator\":\"not_in\",\"values\":[\"homologada\",\"homologacao\"]}.\n"
        "Operadores permitidos: eq, neq, gt, gte, lt, lte, contains, not_contains, in, not_in, is_empty, is_not_empty.\n"
        f"Data atual: {date.today().isoformat()}.\n"
        f"Campos permitidos: {json.dumps(fields, ensure_ascii=False)}.\n"
        f"Formato esperado: {json.dumps(contract, ensure_ascii=False)}.\n"
        f"Defaults do template: {json.dumps(_json_safe(defaults), ensure_ascii=False)}.\n"
        f"Projetos do conector: {json.dumps(connector_projects, ensure_ascii=False)}.\n"
        f"Prompt do usuario:\n{prompt}"
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _call_prompt_interpreter_ai(
    db: Session,
    prompt: str,
    defaults: dict[str, Any],
    connector: Connector | None,
) -> tuple[dict[str, Any], str] | None:
    model = resolve_ai_model(db, "reports")
    if not model.api_key or not model.provider_supported:
        return None
    text = generate_ai_text(
        model,
        system_instruction=(
            "Voce converte prompts de relatorios Redmine em JSON estruturado. "
            "Retorne somente JSON valido, sem markdown."
        ),
        prompt=_build_prompt_interpreter_request(prompt, defaults, connector),
        temperature=0.0,
        max_tokens=2500,
        json_response=True,
    )
    return json.loads(_extract_json_object(text)), model.model_id


def _normalize_prompt_plan(raw_plan: dict[str, Any]) -> dict[str, Any]:
    plan: dict[str, Any] = {}
    if isinstance(raw_plan.get("project_ids"), list):
        plan["project_ids"] = _normalize_project_ids(raw_plan.get("project_ids"))
    if raw_plan.get("query_id") not in (None, "", "-", "null"):
        plan["query_id"] = str(raw_plan.get("query_id"))
    if raw_plan.get("status_id") in ("open", "closed", None):
        plan["status_id"] = raw_plan.get("status_id")
    for key in ("start_date", "end_date"):
        parsed = _parse_date_token(str(raw_plan.get(key))) if raw_plan.get(key) else None
        if parsed:
            plan[key] = parsed
    if isinstance(raw_plan.get("use_saved_query"), bool):
        plan["use_saved_query"] = raw_plan["use_saved_query"]
    columns = []
    if isinstance(raw_plan.get("columns"), list):
        for item in raw_plan["columns"]:
            key = item.get("key") if isinstance(item, dict) else item
            field = _field_from_prompt_label(str(key))
            if field in PROMPT_ALLOWED_FIELDS:
                columns.append({"key": field, "label": PROMPT_FIELD_LABELS.get(field, str(field))})
    if columns:
        plan["columns"] = list({item["key"]: item for item in columns}.values())
    filters = []
    if isinstance(raw_plan.get("filters"), list):
        for item in raw_plan["filters"]:
            if not isinstance(item, dict):
                continue
            field = _field_from_prompt_label(str(item.get("field") or ""))
            operator = str(item.get("operator") or "eq").lower().strip()
            if field not in PROMPT_ALLOWED_FIELDS or operator not in PROMPT_ALLOWED_OPERATORS:
                continue
            rule = {"field": field, "operator": operator}
            if isinstance(item.get("values"), list):
                rule["values"] = [value for value in item["values"] if value not in (None, "")]
            elif item.get("value") not in (None, ""):
                rule["value"] = item.get("value")
            filters.append(rule)
    if filters:
        plan["filters"] = filters
    sort = []
    if isinstance(raw_plan.get("sort"), list):
        for item in raw_plan["sort"]:
            if not isinstance(item, dict):
                continue
            field = _field_from_prompt_label(str(item.get("field") or ""))
            direction = str(item.get("direction") or "asc").lower()
            if field in PROMPT_ALLOWED_FIELDS and direction in {"asc", "desc"}:
                sort.append({"field": field, "direction": direction})
    if sort:
        plan["sort"] = sort
    if isinstance(raw_plan.get("overdue_only"), bool):
        plan["overdue_only"] = raw_plan["overdue_only"]
    return plan


def _apply_prompt_plan(output: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    for key in ("project_ids", "query_id", "status_id", "start_date", "end_date"):
        if key in plan:
            output[key] = plan[key]
    prompt_options = dict(output.get("prompt_options") or {})
    if plan.get("overdue_only"):
        prompt_options["overdue_only"] = True
        prompt_options["sort_overdue_first"] = True
    if plan.get("columns"):
        prompt_options["columns"] = plan["columns"]
    if plan.get("filters"):
        prompt_options["prompt_filters"] = plan["filters"]
        excluded = [
            {"field": rule["field"], "operator": rule["operator"], "values": rule.get("values", [rule.get("value")])}
            for rule in plan["filters"]
            if rule.get("operator") in {"neq", "not_in"}
        ]
        if excluded:
            prompt_options["exclude_field_values"] = excluded
    if plan.get("sort"):
        prompt_options["sort"] = plan["sort"]
    if plan.get("use_saved_query"):
        prompt_options["use_saved_query"] = True
    output["prompt_options"] = prompt_options
    return output


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


def _parse_prompt_filters(
    db: Session,
    prompt: str,
    defaults: dict[str, Any],
    connector: Connector | None = None,
) -> dict[str, Any]:
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

    excluded_field_values = _parse_excluded_field_values(prompt)
    if excluded_field_values:
        output["prompt_options"] = {
            **output["prompt_options"],
            "exclude_field_values": excluded_field_values,
            "prompt_filters": [
                *(output["prompt_options"].get("prompt_filters") or []),
                *excluded_field_values,
            ],
        }
        excluded_status_names = [
            value
            for rule in excluded_field_values
            if rule.get("field") == "status"
            for value in rule.get("values", [])
        ]
        if excluded_status_names:
            output["prompt_options"] = {
                **output["prompt_options"],
                "exclude_status_names": excluded_status_names,
            }

    numeric_filters = _parse_prompt_numeric_filters(prompt)
    if numeric_filters:
        output["prompt_options"] = {
            **output["prompt_options"],
            "prompt_filters": [
                *(output["prompt_options"].get("prompt_filters") or []),
                *numeric_filters,
            ],
        }

    output["prompt_options"] = {
        **output["prompt_options"],
        "columns": _prompt_columns(prompt),
    }

    try:
        ai_result = _call_prompt_interpreter_ai(db, prompt, defaults, connector)
        if ai_result:
            raw_plan, interpreter_model = ai_result
            plan = _normalize_prompt_plan(raw_plan)
            output = _apply_prompt_plan(output, plan)
            output["prompt_options"] = {
                **output["prompt_options"],
                "interpreter": "gemini",
                "interpreter_model": interpreter_model,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("prompt_interpreter_ai_failed", extra={"error": str(exc)})
        cached_options = _cached_prompt_options(defaults, prompt)
        output["prompt_options"] = {
            **output["prompt_options"],
            "interpreter": "fallback",
            "interpreter_error": str(exc),
        }
        if cached_options:
            output["prompt_options"] = {
                **cached_options,
                "interpreter": "cached",
                "interpreter_source": cached_options.get("interpreter", "gemini"),
                "interpreter_error": str(exc),
            }
    else:
        output["prompt_options"] = {
            **output["prompt_options"],
            "interpreter": output["prompt_options"].get("interpreter", "fallback"),
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

    filters = _parse_prompt_filters(db, effective_prompt, template.params_json or {}, connector=connector)
    if not filters["project_ids"]:
        filters["project_ids"] = _default_project_ids(connector)
    if not filters["query_id"] and (
        _should_use_saved_query(effective_prompt)
        or (filters.get("prompt_options") or {}).get("use_saved_query")
    ):
        filters["query_id"] = _select_saved_query(connector, filters["project_ids"], effective_prompt)
        if not filters["query_id"]:
            logger.info("saved_query_not_selected_falling_back_to_project_filters", extra={"template_id": template.id})
    if filters["query_id"] and (
        _should_use_saved_query(effective_prompt)
        or (filters.get("prompt_options") or {}).get("use_saved_query")
    ):
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

    if (filters.get("prompt_options") or {}).get("interpreter") == "gemini":
        template.params_json = {
            **(template.params_json or {}),
            "last_prompt_interpretation": {
                "prompt_hash": _prompt_fingerprint(effective_prompt),
                "prompt_options": filters.get("prompt_options") or {},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    template.last_run_at = datetime.now(timezone.utc)
    template.next_run_at = _next_run_for_template(template)
    db.commit()
    db.refresh(template)
    register_management_event_safe(
        db,
        event_type="ROUTINE_EXECUTED",
        title=f"Relatorio executado: {template.name}",
        description=f"Relatorio #{report.id} gerado a partir do template #{template.id}.",
        source_module="prompt_report",
        source_id=report.id,
        severity="low",
        payload_json={
            "template_id": template.id,
            "template_name": template.name,
            "report_id": report.id,
            "report_status": report.status,
            "trigger": trigger,
            "records": (report.params_json or {}).get("records"),
            "filters": {
                "project_ids": filters.get("project_ids"),
                "status_id": filters.get("status_id"),
                "query_id": filters.get("query_id"),
                "start_date": str(filters.get("start_date")) if filters.get("start_date") else None,
                "end_date": str(filters.get("end_date")) if filters.get("end_date") else None,
            },
        },
    )
    if trigger in {"scheduled", "routine_manual"}:
        _send_prompt_report_notifications(db, template, report, trigger)
    return report, filters


def _send_prompt_report_notifications(db: Session, template: PromptReportTemplate, report: Report, trigger: str) -> None:
    automation = _ensure_prompt_report_automation(db, template)

    run = AutomationRun(
        automation_id=automation.id,
        status="success" if report.status == "completed" else report.status,
        summary_json={
            "message": f"Relatorio #{report.id} gerado",
            "items": 1,
            "tasks": [f"prompt_report:{template.id}"],
            "trigger": trigger,
            "results": [
                {
                    "index": 1,
                    "task": f"prompt_report:{template.id}",
                    "action": "prompt_report",
                    "status": "success" if report.status in {"completed", "completed_with_errors"} else "failed",
                    "message": f"Relatorio #{report.id} gerado",
                    "data": {
                        "template_id": template.id,
                        "report_id": report.id,
                        "report_status": report.status,
                    },
                }
            ],
        },
        finished_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        notifications = send_notifications_for_automation_run(db, automation, run, simulation=False)
        run.summary_json = {
            **(run.summary_json or {}),
            "actionable_notifications": {
                "total": len(notifications),
                "sent": len([item for item in notifications if item.status == "enviado"]),
                "simulated": len([item for item in notifications if item.status == "simulado"]),
                "errors": len([item for item in notifications if item.status == "erro"]),
                "pending_approval": len([item for item in notifications if item.status == "aguardando_aprovacao"]),
            },
        }
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "prompt_report_notifications_failed",
            extra={"template_id": template.id, "report_id": report.id, "automation_id": automation.id, "error": str(exc)},
        )


def _ensure_prompt_report_automation(db: Session, template: PromptReportTemplate) -> Automation:
    key = f"prompt_report_template_{template.id}"
    params_json = {
        "simulation": False,
        "source": "prompt_report_template",
        "prompt_report": {"template_id": template.id},
        "tasks": [f"prompt_report:{template.id}"],
    }
    automation = db.query(Automation).filter(Automation.key == key).first()
    if automation:
        automation.name = template.name
        automation.is_enabled = template.is_enabled
        automation.schedule_cron = None
        automation.next_run_at = None
        automation.params_json = params_json
        db.flush()
        return automation

    automation = Automation(
        key=key,
        name=template.name,
        schedule_cron=None,
        is_enabled=template.is_enabled,
        params_json=params_json,
    )
    db.add(automation)
    db.flush()
    return automation


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
            register_management_event_safe(
                db,
                event_type="ROUTINE_FAILED",
                title=f"Falha ao executar relatorio: {template.name}",
                description=str(exc),
                source_module="prompt_report",
                source_id=template.id,
                severity="high",
                payload_json={
                    "template_id": template.id,
                    "template_name": template.name,
                    "trigger": "scheduled",
                    "error": str(exc),
                },
            )
