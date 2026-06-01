from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

from app.assistant.actions.base import ActionResult
from app.assistant.intent_router import AssistantIntent, _normalize_plan, detect_intent, deterministic_plan
from app.assistant.schemas import AssistantCommand, AssistantPlan
from app.assistant.service import AssistantCoreService
from app.services.prompt_report_service import PromptInterpretationError, _connector_scoped_project_ids, _parse_prompt_filters


def test_detect_list_late_projects_intent():
    assert detect_intent("listar projetos em atraso") == AssistantIntent.LIST_LATE_PROJECTS
    assert detect_intent("quais demandas estao atrasadas?") == AssistantIntent.LIST_LATE_PROJECTS


def test_interpret_create_routine_requires_confirmation():
    plan = deterministic_plan("Crie uma rotina toda sexta as 9h para listar demandas atrasadas.")

    assert plan.intent == "create_routine"
    assert plan.domain == "routines"
    assert plan.action == "create"
    assert plan.requires_confirmation is True
    assert plan.extracted_params["schedule_cron"] == "0 9 * * fri"


def test_redmine_open_demands_command_runs_report_with_confirmation():
    plan = deterministic_plan("consegue me listar as demandas do redmine que estao em aberto do leandro machado")

    assert plan.intent == "run_report"
    assert plan.domain == "reports_redmine"
    assert plan.action == "run_report"
    assert plan.requires_confirmation is True
    assert plan.extracted_params["owner"] == "leandro machado"
    assert plan.extracted_params["status"] == "open"


def test_evaluation_360_command_queries_employee_status():
    plan = deterministic_plan("Como esta avaliacao 360 do leandro montenegro machado")

    assert plan.intent == "get_evaluation_360"
    assert plan.domain == "evaluation"
    assert plan.action == "status"
    assert plan.requires_confirmation is False
    assert plan.extracted_params["employee_name"] == "leandro montenegro machado"


def test_ai_report_action_alias_is_normalized():
    plan = _normalize_plan(
        AssistantPlan(
            intent="list_open_demands_by_user",
            domain="reports_redmine",
            action="list_open_demands_by_user",
            confidence=0.9,
            extracted_params={"owner": "Leandro Machado"},
        )
    )

    assert plan.action == "run_report"
    assert plan.requires_confirmation is True
    assert plan.extracted_params["requested_action"] == "list_open_demands_by_user"


def test_ai_evaluation_action_alias_is_normalized():
    plan = _normalize_plan(
        AssistantPlan(
            intent="get_360_evaluation",
            domain="evaluation",
            action="get_employee_evaluation",
            confidence=0.9,
            extracted_params={"employee_name": "Leandro Montenegro Machado"},
        )
    )

    assert plan.action == "status"
    assert plan.requires_confirmation is False
    assert plan.extracted_params["requested_action"] == "get_employee_evaluation"


def test_ai_meeting_schedule_alias_uses_legacy_meeting_flow():
    plan = _normalize_plan(
        AssistantPlan(
            intent="schedule_meeting",
            domain="meetings",
            action="schedule",
            confidence=0.9,
            extracted_params={"text": "consegue agendar uma reuniao"},
        )
    )

    assert plan.intent == "create_meeting"
    assert plan.domain == "meetings"
    assert plan.action == "create"


def test_capability_question_about_meeting_does_not_execute_schedule():
    db = MagicMock()
    service = AssistantCoreService(db)

    with patch.object(service, "_log"):
        response = service.process_command(
            AssistantCommand(text="consegue agendar uma reuniao?", user_id="1", user_name="Leandro", channel="web"),
            user=MagicMock(id=1, name="Leandro", role="funcionario"),
        )

    assert response.success is True
    assert response.intent == "capability_question"
    assert response.action == "answer"
    assert "nao vou criar nada agora" in response.message


def test_capability_phrase_without_question_mark_does_not_execute_schedule():
    db = MagicMock()
    service = AssistantCoreService(db)

    with patch.object(service, "_log"):
        response = service.process_command(
            AssistantCommand(text="consegue agendar uma reuniao", user_id="1", user_name="Leandro", channel="web"),
            user=MagicMock(id=1, name="Leandro", role="funcionario"),
        )

    assert response.success is True
    assert response.intent == "capability_question"
    assert response.action == "answer"


def test_abbreviated_capability_phrase_does_not_execute_schedule():
    db = MagicMock()
    service = AssistantCoreService(db)

    with patch.object(service, "_log"):
        response = service.process_command(
            AssistantCommand(text="vc consegue agendar uma reuniao no teams ?", user_id="1", user_name="Leandro", channel="web"),
            user=MagicMock(id=1, name="Leandro", role="funcionario"),
        )

    assert response.success is True
    assert response.intent == "capability_question"
    assert response.action == "answer"


def test_direct_meeting_request_still_uses_meeting_flow():
    db = MagicMock()
    service = AssistantCoreService(db)

    with patch.object(service, "_log"):
        response = service.process_command(
            AssistantCommand(text="agende uma reuniao", user_id="1", user_name="Leandro", channel="web"),
            user=MagicMock(id=1, name="Leandro", role="funcionario"),
        )

    assert response.message == "LEGACY_ASSISTANT_FALLBACK"
    assert response.domain == "meetings"


def test_greeting_does_not_continue_pending_input():
    service = AssistantCoreService(MagicMock())
    plan = AssistantPlan(
        intent="run_report",
        domain="reports_redmine",
        action="run_report",
        requires_confirmation=True,
        extracted_params={"text": "pode ser com as demandas do redmine"},
        missing_params=["owner"],
        permission_required="manager",
    )
    action = SimpleNamespace(
        id=77,
        payload_json={"plan": plan.model_dump(), "preview": {"params": plan.extracted_params}},
        status="needs_input",
    )

    assert service._should_continue_pending_input("bom dia", action) is False


def test_system_question_does_not_continue_pending_input():
    db = MagicMock()
    service = AssistantCoreService(db)
    user = MagicMock(id=1, name="Leandro", role="funcionario")
    plan = AssistantPlan(
        intent="run_report",
        domain="reports_redmine",
        action="run_report",
        requires_confirmation=True,
        extracted_params={"text": "pode ser com as demandas do redmine"},
        missing_params=["owner"],
        permission_required="manager",
    )
    action = SimpleNamespace(
        id=77,
        payload_json={"plan": plan.model_dump(), "preview": {"params": plan.extracted_params}},
        status="needs_input",
    )

    with patch.object(service, "_pending_input_action", return_value=action), patch.object(service, "_log"):
        response = service.process_command(
            AssistantCommand(text="o que mais vc pode fazer", user_id="1", user_name="Leandro", channel="web"),
            user=user,
        )

    assert response.success is True
    assert response.action == "capabilities"
    assert "Areas que conheco" in response.message


def test_contextual_name_correction_reuses_previous_report_plan():
    service = AssistantCoreService(MagicMock())
    previous = AssistantPlan(
        intent="run_report",
        domain="reports_redmine",
        action="run_report",
        requires_confirmation=True,
        extracted_params={
            "text": "consegue me listar as demandas do redmine que estao em aberto do leandro machado",
            "owner": "leandro machado",
            "status": "open",
            "template_id": 1,
        },
        permission_required="manager",
    )
    current = AssistantPlan(confidence=0.2)

    with patch.object(service, "_last_contextual_plan", return_value=(previous, 123)):
        plan = service._apply_conversation_context(
            AssistantCommand(text="Coloquei errado o nome e leandro montenegro machado", user_id="1", channel="web"),
            current,
            user=MagicMock(id=1, role="gerente"),
        )

    assert plan.domain == "reports_redmine"
    assert plan.action == "run_report"
    assert plan.requires_confirmation is True
    assert plan.extracted_params["owner"] == "leandro montenegro machado"
    assert plan.extracted_params["template_id"] == 1
    assert "leandro montenegro machado" in plan.extracted_params["text"]
    assert plan.extracted_params["context"]["source"] == "correction"


def test_contextual_source_follow_up_keeps_previous_report_params():
    service = AssistantCoreService(MagicMock())
    previous = AssistantPlan(
        intent="run_report",
        domain="reports_ai",
        action="run_report",
        requires_confirmation=True,
        extracted_params={
            "text": "consegue gerar uma lista com as demandas do Leandro Montenegro Machado",
            "owner": "Leandro Montenegro Machado",
            "template_id": 1,
        },
        permission_required="manager",
    )
    current = AssistantPlan(
        intent="run_report",
        domain="reports_redmine",
        action="run_report",
        requires_confirmation=True,
        extracted_params={"text": "pode ser com as demandas do Redmine", "owner": None, "status": None},
        permission_required="manager",
    )

    with patch.object(service, "_last_contextual_plan", return_value=(previous, 124)):
        plan = service._apply_conversation_context(
            AssistantCommand(text="pode ser com as demandas do Redmine", user_id="1", channel="web"),
            current,
            user=MagicMock(id=1, role="gerente"),
        )

    assert plan.domain == "reports_redmine"
    assert plan.action == "run_report"
    assert plan.extracted_params["owner"] == "Leandro Montenegro Machado"
    assert "Leandro Montenegro Machado" in plan.extracted_params["text"]
    assert "Redmine" in plan.extracted_params["text"]
    assert plan.extracted_params["context"]["source"] == "follow_up"


def test_complete_report_request_does_not_inherit_previous_text_without_context_marker():
    service = AssistantCoreService(MagicMock())
    previous = AssistantPlan(
        intent="run_report",
        domain="reports_redmine",
        action="run_report",
        requires_confirmation=True,
        extracted_params={
            "text": "Pode dizer as demandas que estao em aberto do redmine com 30 dias de atraso.",
            "status": "open",
            "template_id": 1,
        },
        permission_required="manager",
    )
    current = AssistantPlan(
        intent="run_report",
        domain="reports_redmine",
        action="run_report",
        requires_confirmation=True,
        extracted_params={
            "text": "pode gerar um relatorio com as demandas em aberto no redmine do meu setor",
            "status": "open",
            "template_id": 1,
        },
        permission_required="manager",
    )

    with patch.object(service, "_last_contextual_plan", return_value=(previous, 125)):
        plan = service._apply_conversation_context(
            AssistantCommand(text="pode gerar um relatorio com as demandas em aberto no redmine do meu setor", user_id="1", channel="web"),
            current,
            user=MagicMock(id=1, role="gerente"),
        )

    assert plan.extracted_params["text"] == "pode gerar um relatorio com as demandas em aberto no redmine do meu setor"
    assert "30 dias" not in plan.extracted_params["text"]
    assert "context" not in plan.extracted_params


def test_process_read_only_action_executes_without_confirmation():
    db = MagicMock()
    service = AssistantCoreService(db)
    user = MagicMock(id=1, name="Leandro", role="funcionario")

    with patch.object(service, "_log"):
        response = service.process_command(
            AssistantCommand(text="listar projetos em atraso", user_id="1", user_name="Leandro", channel="web"),
            user=user,
        )

    assert response.success is True
    assert response.intent == "list_late_projects"
    assert response.requires_confirmation is False
    assert response.data["total"] == 3


def test_write_action_creates_confirmation_before_execution():
    db = MagicMock()
    service = AssistantCoreService(db)
    user = MagicMock(id=1, name="Gerente", role="gerente")
    pending = SimpleNamespace(id=99, status="needs_confirmation")

    with patch.object(service, "_log"), patch.object(service, "_create_pending_action", return_value=pending):
        response = service.process_command(
            AssistantCommand(text="Crie uma rotina toda sexta as 9h para listar demandas atrasadas.", user_id="1", channel="web"),
            user=user,
        )

    assert response.success is True
    assert response.requires_confirmation is True
    assert response.confirmation_id == "assistant_action:99"
    assert response.action == "create"


def test_confirmation_executes_action():
    db = MagicMock()
    service = AssistantCoreService(db)
    user = MagicMock(id=1, name="Gerente", role="gerente")
    plan = AssistantPlan(
        intent="create_routine",
        domain="routines",
        action="create",
        requires_confirmation=True,
        extracted_params={"name": "Rotina teste"},
        permission_required="manager",
    )
    action = SimpleNamespace(
        id=99,
        user_id=1,
        action_type="routines.create",
        payload_json={"plan": plan.model_dump(), "preview": {"params": plan.extracted_params}},
        result_json={},
        status="needs_confirmation",
        confirmed_at=None,
    )
    handler = MagicMock()
    handler.execute.return_value = ActionResult(message="Rotina criada.", data={"id": 10})

    with patch.object(service, "_action_from_confirmation_id", return_value=action), patch("app.assistant.service.get_action_handler", return_value=handler):
        response = service.confirm("assistant_action:99", True, user=user)

    assert response.success is True
    assert response.message == "Rotina criada."
    assert action.status == "completed"
    assert action.result_json["id"] == 10


def test_pending_input_merge_fills_missing_parameter():
    service = AssistantCoreService(MagicMock())
    previous = AssistantPlan(
        intent="create_employee",
        domain="employees",
        action="create",
        requires_confirmation=True,
        extracted_params={"name": "Joao Silva", "email": None, "setor": "ASM"},
        missing_params=["email"],
        permission_required="admin",
    )
    current = AssistantPlan(confidence=0.2)

    plan = service._merge_pending_plan(previous, current, "o email e joao@empresa.com")

    assert plan.extracted_params["name"] == "Joao Silva"
    assert plan.extracted_params["email"] == "joao@empresa.com"
    assert plan.missing_params == []


def test_permission_denied_for_employee_create():
    db = MagicMock()
    service = AssistantCoreService(db)
    user = MagicMock(id=1, name="Funcionario", role="funcionario")

    with patch.object(service, "_log"):
        response = service.process_command(
            AssistantCommand(text="Cadastre Joao Silva como funcionario do setor ASM com e-mail joao@empresa.com.", user_id="1", channel="web"),
            user=user,
        )

    assert response.success is False
    assert "permission_denied" in response.errors


def test_prompt_report_complex_prompt_requires_ai_or_cached_plan():
    prompt = (
        "Quero um relatÃ³rio que liste as demandas em execuÃ§Ã£o que estÃ£o com o campo data prevista vazia, "
        "ou seja, sem uma data prevista definida, com data de atualizaÃ§Ã£o a mais de 7 dias. "
        "Este relatÃ³rio deve ter os campos tÃ­tulo da demanda, situaÃ§Ã£o, atribuÃ­do para, data prevista e alterado em. "
        "Ordene pelo responsÃ¡vel, ou seja, campo atribuÃ­do para. Quero somente as que estÃ£o em execuÃ§Ã£o "
        "e nÃ£o trazer as demanda que estÃ£o com status homologada ou homologaÃ§Ã£o."
    )

    with patch("app.services.prompt_report_service._call_prompt_interpreter_ai", return_value=None):
        with pytest.raises(PromptInterpretationError) as exc_info:
            _parse_prompt_filters(MagicMock(), prompt, {"project_ids": ["asm-dem"], "status_id": None})
    assert exc_info.value.details["identified"]["project_ids"] == ["asm-dem"]
    assert exc_info.value.details["possible_issues"]
    assert exc_info.value.details["suggestions"]


def test_prompt_report_complex_prompt_uses_ai_plan():
    prompt = "Quero um relatÃ³rio com status HomologaÃ§Ã£o."
    ai_plan = {
        "project_ids": ["asm-dem"],
        "status_id": "open",
        "filters": [{"field": "status", "operator": "in", "values": ["HomologaÃ§Ã£o"]}],
        "columns": [{"key": "subject"}, {"key": "status"}],
        "sort": [{"field": "status", "direction": "asc"}],
    }

    with patch("app.services.prompt_report_service._call_prompt_interpreter_ai", return_value=(ai_plan, "test-model")):
        filters = _parse_prompt_filters(MagicMock(), prompt, {"project_ids": ["asm-dem"], "status_id": "open"})

    assert filters["prompt_options"]["interpreter"] == "gemini"
    assert filters["prompt_options"]["interpreter_model"] == "test-model"
    assert {"field": "status", "operator": "in", "values": ["HomologaÃ§Ã£o"]} in filters["prompt_options"]["prompt_filters"]


def test_prompt_report_drops_spurious_subject_filter_from_ai_plan():
    prompt = (
        "Quero um relatÃ³rio que liste as demandas em execuÃ§Ã£o que estÃ£o em atraso. "
        "NÃ£o trazer as demanda que estÃ£o com status homologada ou homologaÃ§Ã£o."
    )
    ai_plan = {
        "project_ids": ["asm-dem"],
        "status_id": "open",
        "filters": [
            {"field": "due_date", "operator": "lt", "values": ["2026-05-22"]},
            {"field": "status", "operator": "not_in", "values": ["homologada", "homologacao"]},
            {"field": "subject", "operator": "in", "values": ["que estao"]},
        ],
        "overdue_only": True,
    }

    with patch("app.services.prompt_report_service._call_prompt_interpreter_ai", return_value=(ai_plan, "test-model")):
        filters = _parse_prompt_filters(MagicMock(), prompt, {"project_ids": ["asm-dem"], "status_id": "open"})

    prompt_filters = filters["prompt_options"]["prompt_filters"]
    assert {"field": "status", "operator": "not_in", "values": ["homologada", "homologacao"]} in prompt_filters
    assert not any(item.get("field") == "subject" and item.get("values") == ["que estao"] for item in prompt_filters)


def test_prompt_report_projects_are_limited_to_connector_scope():
    connector = SimpleNamespace(config_json={"project_ids": ["asm-dem"]})

    assert _connector_scoped_project_ids(connector, []) == ["asm-dem"]
    assert _connector_scoped_project_ids(connector, ["asm-dem", "outro-projeto"]) == ["asm-dem"]
    assert _connector_scoped_project_ids(connector, ["outro-projeto"]) == ["asm-dem"]


def test_project_advisor_command_is_read_only():
    plan = deterministic_plan("avalie o projeto asm-dem no Redmine")

    assert plan.intent == "analyze_redmine_project"
    assert plan.domain == "project_advisor"
    assert plan.action == "analyze"
    assert plan.requires_confirmation is False
    assert plan.extracted_params["project_id"] == "asm-dem"


def test_project_advisor_missing_project_requests_input():
    plan = deterministic_plan("avalie o projeto no Redmine")

    assert plan.domain == "project_advisor"
    assert plan.action == "analyze"
    assert plan.missing_params == ["project_id"]
