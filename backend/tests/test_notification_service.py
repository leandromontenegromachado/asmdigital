from app.services.notification_service import render_template


def test_render_template_replaces_known_variables():
    output = render_template(
        "Olá, {{nome_responsavel}}. Projeto: {{nome_projeto}}. Vazio: {{inexistente}}",
        {"nome_responsavel": "Maria", "nome_projeto": "Portal"},
    )

    assert "Maria" in output
    assert "Portal" in output
    assert "{{" not in output
