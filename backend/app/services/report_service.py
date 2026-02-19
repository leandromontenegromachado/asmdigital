from __future__ import annotations

import re
import time
from datetime import date
from typing import Any, Iterable

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
            "status": "running",
        },
        status="running",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    rows: list[ReportRow] = []
    errors: list[str] = []

    target_projects = project_ids or [None]
    for project_id in target_projects:
        try:
            issues = adapter.fetch_issues(
                project_id,
                start_date,
                end_date,
                status_id=status_id,
                query_id=query_id,
            )
            for issue in issues:
                extracted = _merge_values(
                    _extract_by_order(issue, mapping_rules)
                )
                options = normalization_rules.get("options", {})
                dictionary = normalization_rules.get("dictionary", normalization_rules)
                normalized = _apply_normalization(extracted, dictionary, options, regex_rules)
                rows.append(
                    ReportRow(
                        report_id=report.id,
                        cliente=normalized.get("cliente"),
                        sistema=normalized.get("sistema"),
                        entrega=normalized.get("entrega"),
                        source_ref=str(issue.get("id")) if issue.get("id") else None,
                        source_url=_issue_url(connector.config_json.get("base_url"), issue.get("id")),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{project_id}: {exc}")

    db.add_all(rows)
    db.commit()

    duration = round((time.time() - started) * 1000)
    report.status = "completed" if not errors else "completed_with_errors"
    report.params_json.update(
        {
            "duration_ms": duration,
            "records": len(rows),
            "errors": errors,
        }
    )
    db.commit()
    db.refresh(report)
    return report


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
