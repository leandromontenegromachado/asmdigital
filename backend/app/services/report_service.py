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

    started = time.time()
    report = Report(
        type="redmine-deliveries",
        params_json={
            "connector_id": connector.id,
            "project_ids": project_ids,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "status_id": status_id,
            "query_id": query_id,
            "prompt_options": prompt_options or {},
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
            issues = list(adapter.fetch_issues(
                project_id,
                start_date,
                end_date,
                status_id=status_id,
                query_id=query_id,
                apply_date_filter=not bool(prompt_options and prompt_options.get("overdue_only")),
            ))
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
                    "redmine_issues": len(issues),
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
                fallback_issues = list(adapter.fetch_issues(
                    project_id,
                    start_date,
                    end_date,
                    status_id=status_id,
                    query_id=None,
                    apply_date_filter=False,
                ))
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
                        "redmine_issues": len(fallback_issues),
                        "rows_after_prompt_filters": len(fallback_rows),
                    }
                )
                project_rows = fallback_rows

            rows.extend(project_rows)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{project_id}: {_format_redmine_error(exc)}")

    if prompt_options and prompt_options.get("sort_overdue_first"):
        rows.sort(key=_report_row_sort_key)

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
        if prompt_options and _is_excluded_by_prompt_rules(metadata, prompt_options.get("exclude_field_values")):
            continue
        if prompt_options and _is_excluded_status(issue, prompt_options.get("exclude_status_names")):
            continue
        extracted = _merge_values(_extract_by_order(issue, mapping_rules))
        options = normalization_rules.get("options", {})
        dictionary = normalization_rules.get("dictionary", normalization_rules)
        normalized = _apply_normalization(extracted, dictionary, options, regex_rules)
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
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


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
    return {
        "source_ref": str(issue.get("id")) if issue.get("id") else None,
        "subject": issue.get("subject"),
        "tracker": _nested_name(issue, "tracker"),
        "status": _nested_name(issue, "status"),
        "priority": _nested_name(issue, "priority"),
        "assigned_to": _nested_name(issue, "assigned_to"),
        "author": _nested_name(issue, "author"),
        "created_on": issue.get("created_on"),
        "updated_on": issue.get("updated_on"),
        "due_date": issue.get("due_date"),
        "done_ratio": issue.get("done_ratio"),
        "is_overdue": _is_overdue(issue),
        "days_overdue": days_overdue,
    }


def _report_row_sort_key(row: ReportRow) -> tuple[int, str, str]:
    raw = row.raw_json or {}
    due_date = str(raw.get("due_date") or "9999-12-31")
    return (0 if raw.get("is_overdue") else 1, due_date, row.source_ref or "")


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
