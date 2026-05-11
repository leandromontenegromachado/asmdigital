from datetime import date, timedelta

from app.services.prompt_report_service import _apply_prompt_plan, _normalize_prompt_plan
from app.services.report_service import _is_rejected_by_prompt_filters


def test_prompt_plan_supports_dynamic_columns_filters_and_sort():
    raw_plan = {
        "columns": ["subject", "assigned_to", "days_overdue"],
        "filters": [
            {"field": "status", "operator": "not_in", "values": ["Homologacao", "Homologada"]},
            {"field": "due_date", "operator": "lt", "value": "today"},
        ],
        "sort": [{"field": "days_overdue", "direction": "desc"}],
    }

    plan = _normalize_prompt_plan(raw_plan)
    output = _apply_prompt_plan(
        {
            "project_ids": [],
            "query_id": None,
            "status_id": None,
            "start_date": None,
            "end_date": None,
            "prompt_options": {},
        },
        plan,
    )

    options = output["prompt_options"]
    assert [column["key"] for column in options["columns"]] == ["subject", "assigned_to", "days_overdue"]
    assert options["prompt_filters"][0]["field"] == "status"
    assert options["prompt_filters"][1]["operator"] == "lt"
    assert options["sort"] == [{"field": "days_overdue", "direction": "desc"}]


def test_prompt_filters_reject_rows_by_any_supported_field():
    rules = [
        {"field": "status", "operator": "not_in", "values": ["Homologacao", "Homologada"]},
        {"field": "priority", "operator": "neq", "value": "Baixa"},
    ]

    assert _is_rejected_by_prompt_filters({"status": "Homologacao", "priority": "Alta"}, rules)
    assert _is_rejected_by_prompt_filters({"status": "Aberta", "priority": "Baixa"}, rules)
    assert not _is_rejected_by_prompt_filters({"status": "Aberta", "priority": "Alta"}, rules)


def test_prompt_filters_compare_dates_against_today():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    rules = [{"field": "due_date", "operator": "lt", "value": "today"}]

    assert not _is_rejected_by_prompt_filters({"due_date": yesterday}, rules)
    assert _is_rejected_by_prompt_filters({"due_date": tomorrow}, rules)
