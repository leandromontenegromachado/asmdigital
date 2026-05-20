from unittest.mock import MagicMock, patch

from app.assistant.intent_router import AssistantIntent, detect_intent
from app.assistant.schemas import AssistantCommand
from app.assistant.service import AssistantCoreService


def test_detect_list_late_projects_intent():
    assert detect_intent("listar projetos em atraso") == AssistantIntent.LIST_LATE_PROJECTS
    assert detect_intent("quais demandas estao atrasadas?") == AssistantIntent.LIST_LATE_PROJECTS


def test_detect_notify_responsibles_intent():
    assert detect_intent("notificar responsaveis dos projetos atrasados") == AssistantIntent.NOTIFY_RESPONSIBLES


def test_process_list_late_projects_returns_structured_data():
    db = MagicMock()
    service = AssistantCoreService(db)
    user = MagicMock(id=1, name="Leandro", role="funcionario")

    with patch.object(service, "_log"):
        response = service.process_command(
            AssistantCommand(text="listar projetos em atraso", user_id="1", user_name="Leandro", channel="web"),
            user=user,
        )

    assert response.success is True
    assert response.intent == "LIST_LATE_PROJECTS"
    assert response.data["total"] == 3
    assert "projetos em atraso" in response.message


def test_notify_responsibles_requires_manager_permission():
    db = MagicMock()
    service = AssistantCoreService(db)
    user = MagicMock(id=1, name="Funcionario", role="funcionario")

    with patch.object(service, "_log"):
        response = service.process_command(
            AssistantCommand(text="notificar responsaveis dos projetos atrasados", user_id="1", channel="web"),
            user=user,
        )

    assert response.success is False
    assert "permission_denied" in response.errors
