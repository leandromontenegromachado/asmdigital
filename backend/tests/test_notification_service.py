from app.models import Employee
from app.services.notification_service import _employee_by_name, _normalize_lookup_text, render_template


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
