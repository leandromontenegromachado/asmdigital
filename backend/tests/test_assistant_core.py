from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.assistant.actions.base import ActionResult
from app.assistant.intent_router import AssistantIntent, detect_intent, deterministic_plan
from app.assistant.schemas import AssistantCommand, AssistantPlan
from app.assistant.service import AssistantCoreService


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
