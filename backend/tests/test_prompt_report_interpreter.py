from datetime import date, timedelta

import pytest

from app.services.prompt_report_service import (
    PromptInterpretationError,
    _apply_prompt_plan,
    _normalize_prompt_plan,
    _parse_prompt_filters,
)
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


def test_complex_status_exclusion_requires_ai_when_no_cache(monkeypatch):
    monkeypatch.setattr("app.services.prompt_report_service.settings.fala_ai_gemini_api_key", None)
    prompt = (
        "Quero um relatorio que liste demandas em atraso, adicionar dias em atraso "
        "e nao trazer demandas com status de homologada e homologacao"
    )

    monkeypatch.setattr("app.services.prompt_report_service._call_prompt_interpreter_ai", lambda *args, **kwargs: None)

    with pytest.raises(PromptInterpretationError):
        _parse_prompt_filters(None, prompt, {})

    assert _is_rejected_by_prompt_filters(
        {"status": "Homologacao"},
        [{"field": "status", "operator": "not_in", "values": ["homologada", "homologacao"]}],
    )


def test_complex_date_prompt_requires_ai_when_no_cache(monkeypatch):
    monkeypatch.setattr("app.services.prompt_report_service.settings.fala_ai_gemini_api_key", None)
    monkeypatch.setattr("app.services.prompt_report_service._call_prompt_interpreter_ai", lambda *args, **kwargs: None)
    prompt = (
        "Quero um relatorio que liste as demandas em execucao com data prevista vazia "
        "e data de atualizacao com mais de 8 dias da data de hoje. Ordene pelo responsavel."
    )

    with pytest.raises(PromptInterpretationError):
        _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})


def test_objective_status_signal_survives_generic_scope_and_ai_null_status(monkeypatch):
    prompt = """# Objetivo
Quero um relatorio que liste as demandas em execucao que estao com o campo data prevista vazio.

## Escopo
- projetos: asm-dem
- status: todos os status
- periodo: sem filtro de data
- query_id: opcional
"""

    monkeypatch.setattr(
        "app.services.prompt_report_service._call_prompt_interpreter_ai",
        lambda *args, **kwargs: (
            {
                "project_ids": ["asm-dem"],
                "status_id": None,
                "filters": [{"field": "due_date", "operator": "is_empty", "values": []}],
            },
            "test-model",
        ),
    )

    filters = _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})

    assert filters["status_id"] == "open"
    assert {"field": "due_date", "operator": "is_empty", "values": []} in filters["prompt_options"]["prompt_filters"]


def test_ai_interpreter_keeps_explicit_local_exclusion_guards(monkeypatch):
    prompt = (
        "Quero um relatório que liste as demandas que estão com data de atualização com mais de 7 dias de hoje. "
        "Este relatório deve ter os campos título da demanda, situação, atribuído para, data prevista e alterado em, nesta ordem. "
        "Não trazer as demanda que estão com status homologada ou homologação ou pendente cliente."
    )

    monkeypatch.setattr(
        "app.services.prompt_report_service._call_prompt_interpreter_ai",
        lambda *args, **kwargs: (
            {
                "project_ids": ["asm-dem"],
                "status_id": None,
                "columns": ["subject", "status", "assigned_to", "due_date", "updated_on"],
                "filters": [{"field": "updated_on", "operator": "lt", "value": "2026-05-21"}],
            },
            "test-model",
        ),
    )

    filters = _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})
    options = filters["prompt_options"]

    assert options["interpreter"] == "gemini"
    assert {"field": "status", "operator": "not_in", "values": ["homologada", "homologacao", "pendente cliente"]} in options["prompt_filters"]
    assert {"field": "status", "operator": "not_in", "values": ["homologada", "homologacao", "pendente cliente"]} in options["exclude_field_values"]


def test_ai_interpreter_supports_days_since_update_column(monkeypatch):
    prompt = (
        "Quero um relatorio que liste demandas com data de atualizacao com mais de 7 dias. "
        "Adicionar uma coluna dias sem atualizacao."
    )

    monkeypatch.setattr(
        "app.services.prompt_report_service._call_prompt_interpreter_ai",
        lambda *args, **kwargs: (
            {
                "project_ids": ["asm-dem"],
                "columns": ["subject", "status", "assigned_to", "due_date", "updated_on", "days_since_update"],
                "filters": [{"field": "updated_on", "operator": "lt", "value": "2026-05-21"}],
            },
            "test-model",
        ),
    )

    filters = _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})
    columns = filters["prompt_options"]["columns"]

    assert [column["key"] for column in columns] == [
        "source_ref",
        "subject",
        "status",
        "assigned_to",
        "due_date",
        "updated_on",
        "days_since_update",
    ]
    assert columns[-1]["label"] == "Dias sem atualização"


def test_explicit_days_since_update_prompt_does_not_become_days_overdue(monkeypatch):
    prompt = "Adicionar uma coluna dias sem atualizacao."

    monkeypatch.setattr(
        "app.services.prompt_report_service._call_prompt_interpreter_ai",
        lambda *args, **kwargs: (
            {
                "project_ids": ["asm-dem"],
                "columns": ["subject", "days_overdue"],
            },
            "test-model",
        ),
    )

    filters = _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})
    column_keys = [column["key"] for column in filters["prompt_options"]["columns"]]

    assert "days_since_update" in column_keys
    assert "days_overdue" not in column_keys


def test_resource_column_prompt_uses_assignee_without_ai(monkeypatch):
    monkeypatch.setattr("app.services.prompt_report_service._call_prompt_interpreter_ai", lambda *args, **kwargs: None)
    prompt = "Trazer as demandas em aberto do recurso Leandro Montenegro Machado. Adiconar a coluna recurso."

    filters = _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})
    options = filters["prompt_options"]

    assert filters["status_id"] == "open"
    assert {"field": "assigned_to", "operator": "contains", "values": ["leandro montenegro machado"]} in options["prompt_filters"]
    assert [column["key"] for column in options["columns"]] == [
        "source_ref",
        "subject",
        "status",
        "assigned_to",
        "due_date",
        "updated_on",
    ]
    assert options["interpreter"] == "fallback"


def test_last_update_column_prompt_uses_updated_on_without_ai(monkeypatch):
    monkeypatch.setattr("app.services.prompt_report_service._call_prompt_interpreter_ai", lambda *args, **kwargs: None)
    prompt = "Trazer as demandas em aberto do recurso Leandro Montenegro Machado. Adicionar uma coluna com a ultima atualizacao"

    filters = _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})
    options = filters["prompt_options"]

    assert filters["status_id"] == "open"
    assert {"field": "assigned_to", "operator": "contains", "values": ["leandro montenegro machado"]} in options["prompt_filters"]
    assert [column["key"] for column in options["columns"]] == [
        "source_ref",
        "subject",
        "status",
        "assigned_to",
        "due_date",
        "updated_on",
    ]
    assert options["interpreter"] == "fallback"


def test_ai_column_only_last_update_does_not_filter_rows(monkeypatch):
    prompt = "Trazer as demandas em aberto do recurso Leandro Montenegro Machado. Adicionar uma coluna com a ultima atualizacao"

    monkeypatch.setattr(
        "app.services.prompt_report_service._call_prompt_interpreter_ai",
        lambda *args, **kwargs: (
            {
                "status_id": "open",
                "columns": ["source_ref", "subject", "assigned_to", "updated_on"],
                "filters": [
                    {"field": "assigned_to", "operator": "contains", "values": ["Leandro Montenegro Machado"]},
                    {"field": "updated_on", "operator": "contains", "values": ["ultima atualizacao"]},
                ],
            },
            "test-model",
        ),
    )

    filters = _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})
    options = filters["prompt_options"]

    assert [column["key"] for column in options["columns"]] == [
        "source_ref",
        "subject",
        "status",
        "assigned_to",
        "due_date",
        "updated_on",
    ]
    assert {"field": "assigned_to", "operator": "contains", "values": ["leandro montenegro machado"]} in options["prompt_filters"]
    assert not any(rule.get("field") == "updated_on" for rule in options["prompt_filters"])
    assert options["interpreter"] == "gemini"


def test_ai_contaminated_assignee_filter_is_removed(monkeypatch):
    prompt = "Trazer as demandas em aberto do recurso Leandro Montenegro Machado. Adicionar uma coluna com a ultima atualizacao"

    monkeypatch.setattr(
        "app.services.prompt_report_service._call_prompt_interpreter_ai",
        lambda *args, **kwargs: (
            {
                "status_id": "open",
                "columns": ["subject", "updated_on"],
                "filters": [
                    {
                        "field": "assigned_to",
                        "operator": "contains",
                        "values": ["leandro montenegro machado. adicionar uma coluna com a ultima atualizacao"],
                    },
                ],
            },
            "test-model",
        ),
    )

    filters = _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})
    options = filters["prompt_options"]

    assert {"field": "assigned_to", "operator": "contains", "values": ["leandro montenegro machado"]} in options["prompt_filters"]
    assert not any(
        "adicionar" in " ".join(str(value) for value in rule.get("values", []))
        for rule in options["prompt_filters"]
        if rule.get("field") == "assigned_to"
    )


def test_ai_implicit_sort_is_removed_when_user_did_not_ask_for_order(monkeypatch):
    prompt = (
        "Trazer as demandas em aberto do recurso Leandro Montenegro Machado. "
        "Adicionar uma coluna com a ultima atualizacao e status"
    )

    monkeypatch.setattr(
        "app.services.prompt_report_service._call_prompt_interpreter_ai",
        lambda *args, **kwargs: (
            {
                "status_id": "open",
                "columns": ["source_ref", "subject", "status", "assigned_to", "due_date", "updated_on"],
                "filters": [{"field": "assigned_to", "operator": "contains", "values": ["Leandro Montenegro Machado"]}],
                "sort": [{"field": "days_overdue", "direction": "desc"}],
            },
            "test-model",
        ),
    )

    filters = _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})

    assert [column["key"] for column in filters["prompt_options"]["columns"]] == [
        "source_ref",
        "subject",
        "status",
        "assigned_to",
        "due_date",
        "updated_on",
    ]
    assert "sort" not in filters["prompt_options"]


def test_ai_explicit_sort_is_kept(monkeypatch):
    prompt = "Trazer demandas em aberto do recurso Leandro Montenegro Machado ordene por data prevista."

    monkeypatch.setattr(
        "app.services.prompt_report_service._call_prompt_interpreter_ai",
        lambda *args, **kwargs: (
            {
                "status_id": "open",
                "columns": ["subject", "due_date"],
                "filters": [{"field": "assigned_to", "operator": "contains", "values": ["Leandro Montenegro Machado"]}],
                "sort": [{"field": "due_date", "direction": "asc"}],
            },
            "test-model",
        ),
    )

    filters = _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})

    assert filters["prompt_options"]["sort"] == [{"field": "due_date", "direction": "asc"}]


def test_ai_date_update_condition_keeps_updated_on_filter(monkeypatch):
    prompt = "Trazer demandas com data de atualizacao com mais de 7 dias. Adicionar coluna ultima atualizacao."

    monkeypatch.setattr(
        "app.services.prompt_report_service._call_prompt_interpreter_ai",
        lambda *args, **kwargs: (
            {
                "columns": ["subject", "updated_on"],
                "filters": [{"field": "updated_on", "operator": "lt", "value": "2026-05-25"}],
            },
            "test-model",
        ),
    )

    filters = _parse_prompt_filters(None, prompt, {"project_ids": ["asm-dem"]})
    options = filters["prompt_options"]

    assert {"field": "updated_on", "operator": "lt", "value": "2026-05-25"} in options["prompt_filters"]
