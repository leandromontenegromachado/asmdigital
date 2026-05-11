from app.models import Automation, AutomationRun, Employee, Notification, NotificationRule, Report, ReportRow
from app.services.notification_service import NOTIFICATION_ERROR, _employee_by_name, _employee_from_item, _item_from_notification, _normalize_lookup_text, _resolve_recipients, retry_notification, render_template


def test_render_template_replaces_known_variables():
    output = render_template(
        "Olá, {{nome_responsavel}}. Projeto: {{nome_projeto}}. Vazio: {{inexistente}}",
        {"nome_responsavel": "Maria", "nome_projeto": "Portal"},
    )

    assert "Maria" in output
    assert "Portal" in output
    assert "{{" not in output


def test_employee_lookup_matches_double_spaces_from_report():
    employee = Employee(id=1, name="Leandro Montenegro Machado", email="leandro@example.com")

    class FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

        def all(self):
            return [employee]

    class FakeDb:
        def query(self, *_args, **_kwargs):
            return FakeQuery()

    assert _employee_by_name(FakeDb(), "Leandro  Montenegro Machado") is employee


def test_employee_lookup_matches_small_typing_difference():
    employee = Employee(id=1, name="Leandro Montenegro Machado", email="leandro@example.com")
    other = Employee(id=2, name="Alessandra Martins Nunes", email="alessandra@example.com")

    class FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

        def all(self):
            return [employee, other]

    class FakeDb:
        def query(self, *_args, **_kwargs):
            return FakeQuery()

    assert _employee_by_name(FakeDb(), "Leandro Montenegor Machado") is employee


def test_employee_lookup_matches_short_registered_name():
    employee = Employee(id=1, name="Leandro Machado", email="leandro@example.com")
    other = Employee(id=2, name="Alessandra Martins Nunes", email="alessandra@example.com")

    class FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

        def all(self):
            return [employee, other]

    class FakeDb:
        def query(self, *_args, **_kwargs):
            return FakeQuery()

    assert _employee_by_name(FakeDb(), "Leandro Montenegro Machado") is employee


def test_employee_lookup_rejects_ambiguous_fuzzy_match():
    first = Employee(id=1, name="Maria Silva Santos", email="maria.santos@example.com")
    second = Employee(id=2, name="Maria Silva Souza", email="maria.souza@example.com")

    class FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

        def all(self):
            return [first, second]

    class FakeDb:
        def query(self, *_args, **_kwargs):
            return FakeQuery()

    assert _employee_by_name(FakeDb(), "Maria Silva") is None


def test_employee_lookup_normalizes_accents_and_case():
    assert _normalize_lookup_text("Homologação") == _normalize_lookup_text("homologacao")


def test_notification_retry_reprocesses_missing_recipient():
    employee = Employee(id=1, name="Leandro Machado", email="leandro@example.com", recebe_notificacao=True, canal_preferencial="email")
    automation = Automation(id=10, name="Teste Demandas em execução")
    run = AutomationRun(id=20, automation_id=10)
    rule = NotificationRule(
        id=30,
        automation_id=10,
        is_active=True,
        recipient_type="responsavel",
        preferred_channel="email",
        requires_approval=False,
        notify_manager=False,
        params_json={},
    )
    notification = Notification(
        id=40,
        execution_id=20,
        automation_id=10,
        channel="email",
        status=NOTIFICATION_ERROR,
        message=str({"assigned_to": "Leandro Montenegro Machado", "status": "Atrasado"}),
        body=str({"assigned_to": "Leandro Montenegro Machado", "status": "Atrasado"}),
        error="Funcionario destinatario nao encontrado.",
    )
    notification.automation = automation
    notification.execution = run

    class RuleQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            return [rule]

    class EmployeeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

        def all(self):
            return [employee]

    class AutomationQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return automation

    class FakeDb:
        def query(self, model):
            if model is NotificationRule:
                return RuleQuery()
            if model is Employee:
                return EmployeeQuery()
            if model is Automation:
                return AutomationQuery()
            raise AssertionError(model)

        def commit(self):
            return None

        def refresh(self, _obj):
            return None

    retry_notification(FakeDb(), notification)

    assert notification.employee_id == employee.id
    assert notification.recipient == employee.email
    assert notification.status == "simulado"


def test_notification_retry_uses_report_rows_when_old_message_has_no_item():
    employee = Employee(id=1, name="Leandro Montenegro Machado", email="leandro@example.com", recebe_notificacao=True, canal_preferencial="email")
    automation = Automation(id=10, name="Teste Demandas em execução")
    run = AutomationRun(
        id=20,
        automation_id=10,
        summary_json={
            "results": [
                {
                    "data": {
                        "report_id": 90,
                    }
                }
            ]
        },
    )
    report = Report(id=90, type="redmine-deliveries")
    row = ReportRow(report_id=90, raw_json={"assigned_to": "Leandro Montenegro Machado", "status": "Atrasado"})
    rule = NotificationRule(
        id=30,
        automation_id=10,
        is_active=True,
        recipient_type="responsavel",
        preferred_channel="email",
        requires_approval=False,
        notify_manager=False,
        params_json={},
    )
    notification = Notification(
        id=40,
        execution_id=20,
        automation_id=10,
        channel="email",
        status=NOTIFICATION_ERROR,
        message="Funcionario destinatario nao encontrado.",
        body="Funcionario destinatario nao encontrado.",
        error="Funcionario destinatario nao encontrado.",
    )
    notification.automation = automation
    notification.execution = run

    class RuleQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            return [rule]

    class EmployeeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

        def all(self):
            return [employee]

    class AutomationQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return automation

    class ReportQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return report

    class ReportRowQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            return [row]

    class FakeDb:
        def query(self, model):
            if model is NotificationRule:
                return RuleQuery()
            if model is Employee:
                return EmployeeQuery()
            if model is Automation:
                return AutomationQuery()
            if model is Report:
                return ReportQuery()
            if model is ReportRow:
                return ReportRowQuery()
            raise AssertionError(model)

        def commit(self):
            return None

        def refresh(self, _obj):
            return None

    retry_notification(FakeDb(), notification)

    assert notification.employee_id == employee.id
    assert notification.recipient == employee.email
    assert notification.status == "simulado"


def test_item_from_notification_accepts_python_dict_string():
    notification = Notification(message="{'assigned_to': 'Leandro Montenegro Machado'}")

    assert _item_from_notification(notification) == {"assigned_to": "Leandro Montenegro Machado"}


def test_fixed_employee_rule_without_employee_falls_back_to_responsible():
    employee = Employee(id=1, name="Leandro Montenegro Machado", email="leandro@example.com")
    rule = NotificationRule(id=1, automation_id=1, recipient_type="funcionario_fixo", params_json={})

    class EmployeeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

        def all(self):
            return [employee]

    class FakeDb:
        def query(self, model):
            assert model is Employee
            return EmployeeQuery()

    assert _resolve_recipients(FakeDb(), rule, {"assigned_to": "Leandro Montenegro Machado"}) == [employee]


def test_employee_lookup_scans_text_when_responsible_key_is_unknown():
    employee = Employee(id=1, name="Leandro Montenegro Machado", email="leandro@example.com")

    class EmployeeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

        def all(self):
            return [employee]

    class FakeDb:
        def query(self, model):
            assert model is Employee
            return EmployeeQuery()

    item = {
        "columns": [
            {"label": "Titulo", "value": "Demanda teste"},
            {"label": "Atribuído para", "value": "Leandro Montenegro Machado"},
        ]
    }

    assert _employee_from_item(FakeDb(), item) is employee
