from __future__ import annotations

import re
import time
import unicodedata
from datetime import date, datetime
from typing import Any, Iterable

import httpx
from sqlalchemy.orm import Session

from app.adapters.redmine import RedmineAdapter
from app.models import Connector, Mapping, Report, ReportRow

DEFAULT_MAPPING_RULES = {
    "sources_order": ["custom_fields", "tags", "subject_regex"],
    "custom_fields": {
        "cliente": "Cliente",
        "sistema": "Sistema",
        "entrega": "Entrega",
    },
    "tags": {
        "cliente": "cliente",
        "sistema": "sistema",
        "entrega": "entrega",
    },
    "subject_regex": {
        "cliente": r"Cliente:\s*([^|]+)",
        "sistema": r"Sistema:\s*([^|]+)",
        "entrega": r"Entrega:\s*([^|]+)",
    },
}

DEFAULT_NORMALIZATION_RULES = {
    "options": {
        "trim": True,
        "uppercase": False,
        "dedupe": True,
    },
    "dictionary": {
        "cliente": {},
        "sistema": {},
        "entrega": {},
    },
}

REDMINE_COLUMN_LABELS = {
    "id": "ID",
    "source_ref": "ID",
    "project": "Projeto",
    "tracker": "Tipo",
    "status": "Status",
    "priority": "Prioridade",
    "subject": "Titulo",
    "author": "Autor",
    "assigned_to": "Atribuido para",
    "updated_on": "Alterado em",
    "created_on": "Criado em",
    "start_date": "Data inicio",
    "due_date": "Data prevista",
    "done_ratio": "% concluido",
    "estimated_hours": "Horas estimadas",
    "spent_hours": "Horas gastas",
    "category": "Categoria",
    "fixed_version": "Versao",
    "days_overdue": "Dias em atraso",
}

REDMINE_COLUMN_ALIASES = {
    "": "",
    "#": "source_ref",
    "id": "source_ref",
    "n": "source_ref",
    "numero": "source_ref",
    "titulo": "subject",
    "assunto": "subject",
    "demanda": "subject",
    "atribuido_para": "assigned_to",
    "atribuida_para": "assigned_to",
    "atribuido": "assigned_to",
    "responsavel": "assigned_to",
    "data_prevista": "due_date",
    "previsto": "due_date",
    "alterado_em": "updated_on",
    "atualizado_em": "updated_on",
    "criado_em": "created_on",
    "data_inicio": "start_date",
    "inicio": "start_date",
    "situacao": "status",
    "tipo": "tracker",
    "versao": "fixed_version",
    "versao_alvo": "fixed_version",
    "categoria": "category",
    "concluido": "done_ratio",
    "percentual_concluido": "done_ratio",
}


def _normalize_column_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", normalized).strip("_").lower()
    return normalized


def _normalize_redmine_columns(raw_columns: Any) -> list[dict[str, str]]:
    if not isinstance(raw_columns, list):
        return []
    columns: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_columns:
        if isinstance(item, dict):
            raw_key = item.get("key") or item.get("name") or item.get("field") or item.get("caption") or item.get("label")
            raw_label = item.get("label") or item.get("caption") or item.get("name") or raw_key
        else:
            raw_key = item
            raw_label = item
        key = _normalize_column_key(raw_key)
        key = REDMINE_COLUMN_ALIASES.get(key, key)
        if not key or key in seen:
            continue
        seen.add(key)
        label = str(raw_label or REDMINE_COLUMN_LABELS.get(key) or key).strip()
        columns.append({"key": key, "label": REDMINE_COLUMN_LABELS.get(key, label)})
    return columns


def _load_saved_query_columns(adapter: RedmineAdapter, project_ids: list[str], query_id: str | None) -> list[dict[str, str]]:
    if not query_id:
        return []
    candidates: list[dict[str, Any]] = []
    for project_id in project_ids or [None]:
        try:
            candidates.extend(adapter.fetch_queries(project_id=project_id))
        except Exception:  # noqa: BLE001
            continue
    for query in candidates:
        if str(query.get("id")) != str(query_id):
            continue
        columns = _normalize_redmine_columns(query.get("columns") or query.get("column_names"))
        if columns:
            return columns
    for project_id in project_ids or [None]:
        try:
            columns = _normalize_redmine_columns(adapter.fetch_query_columns(project_id, query_id))
        except Exception:  # noqa: BLE001
            continue
        if columns:
            return columns
    return []


def _get_mapping(db: Session, mapping_type: str, connector_id: int | None = None) -> dict[str, Any]:
    query = db.query(Mapping).filter(Mapping.mapping_type == mapping_type)
    if connector_id:
        query = query.filter(Mapping.connector_id == connector_id)
    mapping = query.order_by(Mapping.updated_at.desc()).first()
    if mapping:
        return mapping.rules_json
    if mapping_type == "redmine_fields":
        return DEFAULT_MAPPING_RULES
    if mapping_type == "normalization_dictionary":
        return DEFAULT_NORMALIZATION_RULES
    if mapping_type == "regex_rules":
        return {}
    return {}


def _extract_from_custom_fields(issue: dict[str, Any], fields_map: dict[str, str]) -> dict[str, str | None]:
    custom_fields = issue.get("custom_fields", []) or []
    field_lookup = {field.get("name"): field.get("value") for field in custom_fields}
    result = {}
    for key, name in fields_map.items():
        result[key] = field_lookup.get(name)
    return result


def _extract_from_tags(issue: dict[str, Any], tag_prefixes: dict[str, str]) -> dict[str, str | None]:
    tags = issue.get("tags") or issue.get("labels") or []
    normalized = []
    for tag in tags:
        if isinstance(tag, dict):
            value = tag.get("name")
        else:
            value = tag
        if value:
            normalized.append(str(value))
    result: dict[str, str | None] = {"cliente": None, "sistema": None, "entrega": None}
    for field, prefix in tag_prefixes.items():
        for tag in normalized:
            if tag.lower().startswith(prefix.lower() + ":"):
                result[field] = tag.split(":", 1)[1].strip()
                break
    return result


def _extract_from_subject_regex(issue: dict[str, Any], patterns: dict[str, str]) -> dict[str, str | None]:
    subject = issue.get("subject") or ""
    result: dict[str, str | None] = {"cliente": None, "sistema": None, "entrega": None}
    for field, pattern in patterns.items():
        match = re.search(pattern, subject, flags=re.IGNORECASE)
        if match:
            result[field] = match.group(1).strip()
    return result


def _apply_regex(value: str, pattern: str | None, replacement: str | None) -> str:
    if not pattern:
        return value
    try:
        return re.sub(pattern, replacement or "", value)
    except re.error:
        return value


def _dedupe_words(value: str) -> str:
    parts = value.split()
    seen = set()
    result = []
    for part in parts:
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(part)
    return " ".join(result)


def _apply_normalization(
    values: dict[str, str | None],
    normalization: dict[str, dict[str, str]],
    options: dict[str, bool],
    regex_rule: dict[str, str | bool] | None,
) -> dict[str, str | None]:
    normalized = {}
    for field, value in values.items():
        if value is None:
            normalized[field] = None
            continue
        next_value = value
        if options.get("trim", False):
            next_value = next_value.strip()
        if regex_rule and regex_rule.get("enabled"):
            next_value = _apply_regex(
                next_value,
                str(regex_rule.get("pattern", "")) or None,
                str(regex_rule.get("replacement", "")) if regex_rule.get("replacement") is not None else None,
            )
        if options.get("uppercase", False):
            next_value = next_value.upper()
        if options.get("dedupe", False):
            next_value = _dedupe_words(next_value)
        mapping = normalization.get(field, {})
        normalized[field] = mapping.get(next_value, next_value)
    return normalized


def _merge_values(values_list: Iterable[dict[str, str | None]]) -> dict[str, str | None]:
    result: dict[str, str | None] = {"cliente": None, "sistema": None, "entrega": None}
    for values in values_list:
        for key, value in values.items():
            if result.get(key) is None and value:
                result[key] = value
    return result


def _merge_values_with_source(
    values_list: Iterable[tuple[str, dict[str, str | None]]]
) -> dict[str, dict[str, str | None]]:
    result: dict[str, dict[str, str | None]] = {
        "cliente": {"value": None, "source": None},
        "sistema": {"value": None, "source": None},
        "entrega": {"value": None, "source": None},
    }
    for source, values in values_list:
        for key, value in values.items():
            if result[key]["value"] is None and value:
                result[key]["value"] = value
                result[key]["source"] = source
    return result


def _configured_project_ids(connector: Connector) -> list[str]:
    raw_projects = (connector.config_json or {}).get("project_ids")
    if not isinstance(raw_projects, list):
        return []
    return [str(item).strip().lower() for item in raw_projects if str(item).strip()]


def _connector_scoped_project_ids(connector: Connector, requested_project_ids: list[str]) -> list[str]:
    connector_projects = _configured_project_ids(connector)
    requested = [str(item).strip().lower() for item in requested_project_ids or [] if str(item).strip()]
    if not connector_projects:
        return requested
    if not requested:
        return connector_projects
    allowed = set(connector_projects)
    scoped = [project_id for project_id in requested if project_id in allowed]
    return scoped or connector_projects


def _normalize_project_scope_value(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-zA-Z0-9]+", "", normalized).casefold()


def _project_scope_tokens(value: Any) -> list[str]:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return [token.casefold() for token in re.split(r"[^a-zA-Z0-9]+", normalized) if token]


def _project_scope_matches(expected: Any, candidate: Any) -> bool:
    expected_compact = _normalize_project_scope_value(expected)
    candidate_compact = _normalize_project_scope_value(candidate)
    if not expected_compact or not candidate_compact:
        return False
    if expected_compact == candidate_compact:
        return True

    expected_tokens = _project_scope_tokens(expected)
    candidate_tokens = _project_scope_tokens(candidate)
    if len(expected_tokens) != len(candidate_tokens):
        return False
    return all(
        left == right
        or (len(left) >= 3 and right.startswith(left))
        or (len(right) >= 3 and left.startswith(right))
        for left, right in zip(expected_tokens, candidate_tokens)
    )


def _issue_matches_project_scope(issue: dict[str, Any], project_id: str | None) -> bool:
    if not project_id:
        return True
    project = issue.get("project")
    if not isinstance(project, dict):
        return _project_scope_matches(project_id, project)

    candidates = [
        project.get("id"),
        project.get("identifier"),
        project.get("name"),
    ]
    return any(_project_scope_matches(project_id, item) for item in candidates if item not in (None, ""))


def generate_redmine_report(
    db: Session,
    connector: Connector,
    project_ids: list[str],
    start_date: date,
    end_date: date,
    status_id: str | None = None,
    query_id: str | None = None,
    prompt_options: dict[str, Any] | None = None,
) -> Report:
    mapping_rules = _get_mapping(db, "redmine_fields", connector_id=connector.id)
    normalization_rules = _get_mapping(db, "normalization_dictionary", connector_id=connector.id)
    regex_rules = _get_mapping(db, "regex_rules", connector_id=connector.id)

    base_url = connector.config_json.get("base_url")
    api_key = connector.config_json.get("api_key")
    if not base_url or not api_key:
        raise ValueError("Connector config missing base_url or api_key")

    adapter = RedmineAdapter(base_url=base_url, api_key=api_key)
    prompt_options = dict(prompt_options or {})
    project_ids = _connector_scoped_project_ids(connector, project_ids)
    saved_query_columns = _load_saved_query_columns(adapter, project_ids, query_id) if query_id else []
    if saved_query_columns and not prompt_options.get("columns"):
        prompt_options["columns"] = saved_query_columns
    ignore_date_filter = bool(prompt_options.get("ignore_date_filter") or prompt_options.get("overdue_only"))

    started = time.time()
    report = Report(
        type="redmine-deliveries",
        params_json={
            "connector_id": connector.id,
            "project_ids": project_ids,
            "start_date": None if ignore_date_filter else str(start_date),
            "end_date": None if ignore_date_filter else str(end_date),
            "status_id": status_id,
            "query_id": query_id,
            "prompt_options": prompt_options,
            "display_columns": saved_query_columns,
            "status": "running",
        },
        status="running",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    rows: list[ReportRow] = []
    errors: list[str] = []
    diagnostics: list[dict[str, Any]] = []

    target_projects = project_ids or [None]
    for project_id in target_projects:
        try:
            redmine_issues = list(adapter.fetch_issues(
                project_id,
                start_date,
                end_date,
                status_id=status_id,
                query_id=query_id,
                apply_date_filter=not ignore_date_filter,
            ))
            issues = [issue for issue in redmine_issues if _issue_matches_project_scope(issue, project_id)]
            project_rows = _issues_to_report_rows(
                report_id=report.id,
                issues=issues,
                connector=connector,
                mapping_rules=mapping_rules,
                normalization_rules=normalization_rules,
                regex_rules=regex_rules,
                prompt_options=prompt_options,
            )
            diagnostics.append(
                {
                    "project_id": project_id,
                    "query_id": query_id,
                    "source": "saved_query" if query_id else "direct_filters",
                    "redmine_issues": len(redmine_issues),
                    "rows_after_project_scope": len(issues),
                    "rows_after_prompt_filters": len(project_rows),
                }
            )

            if (
                not project_rows
                and query_id
                and status_id == "open"
                and prompt_options
                and prompt_options.get("overdue_only")
            ):
                redmine_fallback_issues = list(adapter.fetch_issues(
                    project_id,
                    start_date,
                    end_date,
                    status_id=status_id,
                    query_id=None,
                    apply_date_filter=False,
                ))
                fallback_issues = [
                    issue for issue in redmine_fallback_issues if _issue_matches_project_scope(issue, project_id)
                ]
                fallback_rows = _issues_to_report_rows(
                    report_id=report.id,
                    issues=fallback_issues,
                    connector=connector,
                    mapping_rules=mapping_rules,
                    normalization_rules=normalization_rules,
                    regex_rules=regex_rules,
                    prompt_options=prompt_options,
                )
                diagnostics.append(
                    {
                        "project_id": project_id,
                        "query_id": None,
                        "source": "direct_filters_fallback",
                        "reason": "saved_query_returned_no_rows_after_prompt_filters",
                        "redmine_issues": len(redmine_fallback_issues),
                        "rows_after_project_scope": len(fallback_issues),
                        "rows_after_prompt_filters": len(fallback_rows),
                    }
                )
                project_rows = fallback_rows

            rows.extend(project_rows)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{project_id}: {_format_redmine_error(exc)}")

    if prompt_options and prompt_options.get("sort_overdue_first"):
        rows.sort(key=_report_row_sort_key)
    elif prompt_options and prompt_options.get("sort"):
        rows.sort(key=lambda row: _prompt_sort_key(row, prompt_options.get("sort")))

    db.add_all(rows)
    db.commit()

    duration = round((time.time() - started) * 1000)
    report.status = "completed" if not errors else ("failed" if not rows else "completed_with_errors")
    report.params_json = {
        **(report.params_json or {}),
        "duration_ms": duration,
        "records": len(rows),
        "errors": errors,
        "diagnostics": diagnostics,
    }
    db.commit()
    db.refresh(report)
    return report


def _issues_to_report_rows(
    report_id: int,
    issues: Iterable[dict[str, Any]],
    connector: Connector,
    mapping_rules: dict[str, Any],
    normalization_rules: dict[str, Any],
    regex_rules: dict[str, Any],
    prompt_options: dict[str, Any] | None = None,
) -> list[ReportRow]:
    rows: list[ReportRow] = []
    for issue in issues:
        metadata = _issue_report_metadata(issue)
        if prompt_options and prompt_options.get("overdue_only") and not _is_overdue(issue):
            continue
        if prompt_options and _is_rejected_by_prompt_filters(metadata, prompt_options.get("prompt_filters")):
            continue
        if prompt_options and _is_excluded_by_prompt_rules(metadata, prompt_options.get("exclude_field_values")):
            continue
        if prompt_options and _is_excluded_status(issue, prompt_options.get("exclude_status_names")):
            continue
        extracted = _merge_values(_extract_by_order(issue, mapping_rules))
        options = normalization_rules.get("options", {})
        dictionary = normalization_rules.get("dictionary", normalization_rules)
        normalized = _apply_normalization(extracted, dictionary, options, regex_rules)
        if prompt_options and _is_rejected_by_prompt_filters({**metadata, **normalized}, prompt_options.get("prompt_filters")):
            continue
        if prompt_options and _is_excluded_by_prompt_rules({**metadata, **normalized}, prompt_options.get("exclude_field_values")):
            continue
        rows.append(
            ReportRow(
                report_id=report_id,
                cliente=normalized.get("cliente"),
                sistema=normalized.get("sistema"),
                entrega=normalized.get("entrega"),
                source_ref=str(issue.get("id")) if issue.get("id") else None,
                source_url=_issue_url(connector.config_json.get("base_url"), issue.get("id")),
                raw_json=metadata,
            )
        )
    return rows


def _extract_by_order(issue: dict[str, Any], mapping_rules: dict[str, Any]) -> list[dict[str, str | None]]:
    order = mapping_rules.get("sources_order", [])
    values = []
    for source in order:
        if source == "custom_fields":
            values.append(_extract_from_custom_fields(issue, mapping_rules.get("custom_fields", {})))
        elif source == "tags":
            values.append(_extract_from_tags(issue, mapping_rules.get("tags", {})))
        elif source == "subject_regex":
            values.append(_extract_from_subject_regex(issue, mapping_rules.get("subject_regex", {})))
    return values


def _parse_redmine_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)
    for pattern in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _format_redmine_error(exc: Exception) -> str:
    if isinstance(exc, httpx.ConnectError):
        request = getattr(exc, "request", None)
        url = str(request.url) if request else ""
        return f"falha de conexao com o Redmine{f' em {url}' if url else ''}: {exc}"
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
    return f"HTTP {response.status_code} ao consultar {response.url}: {response.text[:300]}"
    if isinstance(exc, httpx.RequestError):
        request = getattr(exc, "request", None)
        url = str(request.url) if request else ""
        return f"erro de rede ao consultar Redmine{f' em {url}' if url else ''}: {exc}"
    return str(exc)


def _nested_name(issue: dict[str, Any], key: str) -> str | None:
    value = issue.get(key)
    if isinstance(value, dict):
        return value.get("name")
    return str(value) if value else None


def _normalize_filter_text(value: Any) -> str:
    text = str(value or "").strip()
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char)).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _is_excluded_status(issue: dict[str, Any], excluded_status_names: Any) -> bool:
    if not isinstance(excluded_status_names, list) or not excluded_status_names:
        return False
    status_name = _normalize_filter_text(_nested_name(issue, "status"))
    excluded = {_normalize_filter_text(item) for item in excluded_status_names if str(item).strip()}
    return bool(status_name and status_name in excluded)


def _is_excluded_by_prompt_rules(metadata: dict[str, Any], rules: Any) -> bool:
    if not isinstance(rules, list):
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        field = str(rule.get("field") or "").strip()
        operator = str(rule.get("operator") or "neq").strip().lower()
        values = rule.get("values")
        if not field or not isinstance(values, list):
            continue
        actual = _normalize_filter_text(metadata.get(field))
        expected = [_normalize_filter_text(value) for value in values if str(value).strip()]
        if not actual or not expected:
            continue
        if operator in {"neq", "not_eq", "not_in"} and actual in expected:
            return True
        if operator == "not_contains" and any(value in actual for value in expected):
            return True
    return False


def _rule_values(rule: dict[str, Any]) -> list[Any]:
    if isinstance(rule.get("values"), list):
        return [value for value in rule["values"] if value not in (None, "")]
    if rule.get("value") not in (None, ""):
        return [rule.get("value")]
    return []


def _as_number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "").strip().lower()
    if text in {"today", "hoje"}:
        return date.today()
    return _parse_redmine_date(text)


def _compare_values(actual: Any, expected: Any, operator: str) -> bool:
    actual_text = _normalize_filter_text(actual)
    expected_text = _normalize_filter_text(expected)
    if operator in {"eq", "neq", "contains", "not_contains", "in", "not_in"}:
        if operator == "eq":
            return actual_text == expected_text
        if operator == "neq":
            return actual_text != expected_text
        if operator == "contains":
            return bool(expected_text and expected_text in actual_text)
        if operator == "not_contains":
            return not expected_text or expected_text not in actual_text
        if operator == "in":
            return actual_text == expected_text
        if operator == "not_in":
            return actual_text != expected_text

    actual_number = _as_number(actual)
    expected_number = _as_number(expected)
    if actual_number is not None and expected_number is not None:
        if operator == "gt":
            return actual_number > expected_number
        if operator == "gte":
            return actual_number >= expected_number
        if operator == "lt":
            return actual_number < expected_number
        if operator == "lte":
            return actual_number <= expected_number

    actual_date = _as_date(actual)
    expected_date = _as_date(expected)
    if actual_date and expected_date:
        if operator == "gt":
            return actual_date > expected_date
        if operator == "gte":
            return actual_date >= expected_date
        if operator == "lt":
            return actual_date < expected_date
        if operator == "lte":
            return actual_date <= expected_date
    return False


def _rule_matches(metadata: dict[str, Any], rule: dict[str, Any]) -> bool | None:
    field = str(rule.get("field") or "").strip()
    operator = str(rule.get("operator") or "eq").strip().lower()
    if not field or field not in metadata:
        return None
    actual = metadata.get(field)
    if operator == "is_empty":
        return actual in (None, "")
    if operator == "is_not_empty":
        return actual not in (None, "")
    values = _rule_values(rule)
    if not values:
        return True
    if operator in {"neq", "not_contains", "not_in"}:
        return all(_compare_values(actual, value, operator) for value in values)
    return any(_compare_values(actual, value, operator) for value in values)


def _is_rejected_by_prompt_filters(metadata: dict[str, Any], rules: Any) -> bool:
    if not isinstance(rules, list):
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        matched = _rule_matches(metadata, rule)
        if matched is False:
            return True
    return False


def _is_closed(issue: dict[str, Any]) -> bool:
    status = issue.get("status")
    if isinstance(status, dict):
        return bool(status.get("is_closed")) or str(status.get("name", "")).lower() in {"fechado", "closed"}
    return False


def _is_overdue(issue: dict[str, Any]) -> bool:
    due_date = _parse_redmine_date(issue.get("due_date"))
    return bool(due_date and due_date < date.today() and not _is_closed(issue))


def _issue_report_metadata(issue: dict[str, Any]) -> dict[str, Any]:
    due_date = _parse_redmine_date(issue.get("due_date"))
    days_overdue = (date.today() - due_date).days if due_date and due_date < date.today() else 0
    metadata = {
        "source_ref": str(issue.get("id")) if issue.get("id") else None,
        "id": str(issue.get("id")) if issue.get("id") else None,
        "subject": issue.get("subject"),
        "project": _nested_name(issue, "project"),
        "tracker": _nested_name(issue, "tracker"),
        "status": _nested_name(issue, "status"),
        "priority": _nested_name(issue, "priority"),
        "assigned_to": _nested_name(issue, "assigned_to"),
        "author": _nested_name(issue, "author"),
        "created_on": issue.get("created_on"),
        "updated_on": issue.get("updated_on"),
        "start_date": issue.get("start_date"),
        "due_date": issue.get("due_date"),
        "done_ratio": issue.get("done_ratio"),
        "estimated_hours": issue.get("estimated_hours"),
        "spent_hours": issue.get("spent_hours"),
        "category": _nested_name(issue, "category"),
        "fixed_version": _nested_name(issue, "fixed_version"),
        "is_overdue": _is_overdue(issue),
        "days_overdue": days_overdue,
    }
    for custom_field in issue.get("custom_fields") or []:
        if not isinstance(custom_field, dict):
            continue
        value = custom_field.get("value")
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        field_id = custom_field.get("id")
        field_name = custom_field.get("name")
        if field_id is not None:
            metadata[f"cf_{field_id}"] = value
        normalized_name = _normalize_column_key(field_name)
        if normalized_name:
            metadata[normalized_name] = value
    return metadata


def _report_row_sort_key(row: ReportRow) -> tuple[int, str, str]:
    raw = row.raw_json or {}
    due_date = str(raw.get("due_date") or "9999-12-31")
    return (0 if raw.get("is_overdue") else 1, due_date, row.source_ref or "")


def _prompt_sort_key(row: ReportRow, sort_rules: Any) -> tuple[Any, ...]:
    raw = row.raw_json or {}
    context = {
        **raw,
        "cliente": row.cliente,
        "sistema": row.sistema,
        "entrega": row.entrega,
        "source_ref": row.source_ref,
    }
    if not isinstance(sort_rules, list):
        return (row.source_ref or "",)
    values: list[Any] = []
    for rule in sort_rules:
        if not isinstance(rule, dict):
            continue
        field = str(rule.get("field") or "").strip()
        value = context.get(field)
        number = _as_number(value)
        parsed_date = _as_date(value)
        comparable: Any = number if number is not None else parsed_date or _normalize_filter_text(value)
        if str(rule.get("direction") or "asc").lower() == "desc":
            if isinstance(comparable, (int, float)):
                comparable = -comparable
            elif isinstance(comparable, date):
                comparable = date.max - (comparable - date.min)
            else:
                comparable = "".join(chr(255 - ord(char)) for char in str(comparable))
        values.append(comparable)
    values.append(row.source_ref or "")
    return tuple(values)


def _extract_by_order_with_source(issue: dict[str, Any], mapping_rules: dict[str, Any]) -> list[tuple[str, dict[str, str | None]]]:
    order = mapping_rules.get("sources_order", [])
    values = []
    for source in order:
        if source == "custom_fields":
            values.append((source, _extract_from_custom_fields(issue, mapping_rules.get("custom_fields", {}))))
        elif source == "tags":
            values.append((source, _extract_from_tags(issue, mapping_rules.get("tags", {}))))
        elif source == "subject_regex":
            values.append((source, _extract_from_subject_regex(issue, mapping_rules.get("subject_regex", {}))))
    return values


def build_preview_tickets(
    db: Session,
    connector: Connector,
    project_id: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    mapping_rules = _get_mapping(db, "redmine_fields", connector_id=connector.id)
    normalization_rules = _get_mapping(db, "normalization_dictionary", connector_id=connector.id)
    regex_rules = _get_mapping(db, "regex_rules", connector_id=connector.id)

    base_url = connector.config_json.get("base_url")
    api_key = connector.config_json.get("api_key")
    if not base_url or not api_key:
        raise ValueError("Connector config missing base_url or api_key")

    adapter = RedmineAdapter(base_url=base_url, api_key=api_key)

    end_date = date.today()
    start_date = end_date.replace(day=1)
    tickets = []
    for issue in adapter.fetch_issues(project_id, start_date, end_date):
        extracted = _merge_values_with_source(_extract_by_order_with_source(issue, mapping_rules))
        options = normalization_rules.get("options", {})
        dictionary = normalization_rules.get("dictionary", normalization_rules)
        normalized = _apply_normalization(
            {k: extracted[k]["value"] for k in extracted},
            dictionary,
            options,
            regex_rules,
        )
        tickets.append(
            {
                "id": str(issue.get("id")),
                "title": f"#{issue.get('id')} - {issue.get('subject', '')}",
                "cliente": {
                    "raw": extracted["cliente"]["value"],
                    "processed": normalized.get("cliente"),
                    "source": extracted["cliente"]["source"],
                    "is_warning": normalized.get("cliente") is None,
                },
                "sistema": {
                    "raw": extracted["sistema"]["value"],
                    "processed": normalized.get("sistema"),
                    "source": extracted["sistema"]["source"],
                    "is_warning": normalized.get("sistema") is None,
                },
                "entrega": {
                    "raw": extracted["entrega"]["value"],
                    "processed": normalized.get("entrega"),
                    "source": extracted["entrega"]["source"],
                    "is_warning": normalized.get("entrega") is None,
                },
                "source_ref": str(issue.get("id")) if issue.get("id") else None,
                "source_url": _issue_url(base_url, issue.get("id")),
            }
        )
        if len(tickets) >= limit:
            break
    return tickets


def _issue_url(base_url: str | None, issue_id: Any) -> str | None:
    if not base_url or not issue_id:
        return None
    return f"{base_url.rstrip('/')}/issues/{issue_id}"
