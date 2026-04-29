from types import SimpleNamespace

import pytest

from app.services.ai_feedback_analysis_service import AiFeedbackAnalysisService
from app.services.csv_evaluation_import_service import CsvEvaluationImportService


def test_csv_score_conversion_from_1_to_5_scale():
    assert CsvEvaluationImportService.normalize_score("1") == 0
    assert CsvEvaluationImportService.normalize_score("3") == 50
    assert CsvEvaluationImportService.normalize_score("5") == 100


def test_csv_score_keeps_0_to_100_scale():
    assert CsvEvaluationImportService.normalize_score("87,5") == 87.5


def test_csv_score_accepts_asm_text_labels():
    assert CsvEvaluationImportService.normalize_score("Bom") == 50
    assert CsvEvaluationImportService.normalize_score("Muito Bom") == 75
    assert CsvEvaluationImportService.normalize_score("Destacado") == 100
    assert CsvEvaluationImportService.normalize_score("Insatisfatório") == 0


def test_csv_row_mapping_and_competency_average():
    service = CsvEvaluationImportService(db=SimpleNamespace(), actor_id=1)
    normalized = service._normalize_row(
        {
            "Avaliado email": "ana@company.com",
            "Avaliado nome": "Ana",
            "Avaliador email": "bruno@company.com",
            "Avaliador nome": "Bruno",
            "Relacao": "par",
            "Comunicacao": "4",
            "Equipe": "5",
            "Fortes": "Colabora bem",
        },
        {
            "evaluated_email": "Avaliado email",
            "evaluated_name": "Avaliado nome",
            "evaluator_email": "Avaliador email",
            "evaluator_name": "Avaliador nome",
            "relation_type": "Relacao",
            "communication_score": "Comunicacao",
            "teamwork_score": "Equipe",
            "strengths_comment": "Fortes",
        },
    )

    assert normalized["relation_type"] == "PEER"
    assert normalized["communication_score"] == 75
    assert normalized["teamwork_score"] == 100
    assert normalized["general_score"] == 87.5
    assert normalized["strengths_comment"] == "Colabora bem"


def test_csv_row_mapping_without_evaluated_email_and_relation_uses_defaults():
    service = CsvEvaluationImportService(db=SimpleNamespace(), actor_id=1)
    normalized = service._normalize_row(
        {
            "Avaliado": "ANDERSON MACHADO",
            "Email": "alessandra@company.com",
            "Avaliador": "Alessandra",
            "Comunicacao": "Muito Bom",
            "Equipe": "Destacado",
        },
        {
            "evaluated_name": "Avaliado",
            "evaluator_email": "Email",
            "evaluator_name": "Avaliador",
            "communication_score": "Comunicacao",
            "teamwork_score": "Equipe",
        },
    )

    assert normalized["evaluated_email"] == "anderson.machado@evaluation.asmdigital.com"
    assert normalized["relation_type"] == "PEER"
    assert normalized["general_score"] == 87.5


def test_csv_reader_detects_comma_csv_headers():
    service = CsvEvaluationImportService(db=SimpleNamespace(), actor_id=1)
    headers, rows = service._read_tabular_file("avaliacao.csv", b"Nome,Nota\nAna,Bom\n")

    assert headers == ["Nome", "Nota"]
    assert rows[0]["Nota"] == "Bom"


def test_csv_row_validation_requires_score():
    service = CsvEvaluationImportService(db=SimpleNamespace(), actor_id=1)
    with pytest.raises(ValueError, match="general_score"):
        service._normalize_row(
            {
                "Avaliado email": "ana@company.com",
                "Avaliado nome": "Ana",
                "Avaliador email": "bruno@company.com",
                "Avaliador nome": "Bruno",
                "Relacao": "GESTOR",
            },
            {
                "evaluated_email": "Avaliado email",
                "evaluated_name": "Avaliado nome",
                "evaluator_email": "Avaliador email",
                "evaluator_name": "Avaliador nome",
                "relation_type": "Relacao",
            },
        )


def test_ai_json_validation_accepts_expected_schema():
    payload = {
        "employee_id": "1",
        "summary": "Resumo",
        "strengths": ["Entrega"],
        "attention_points": ["Comunicação"],
        "recurring_themes": ["Autonomia"],
        "qualitative_alerts": [{"type": "DIVERGENCE", "description": "Divergencia", "severity": "MEDIUM"}],
        "suggested_feedback": "Feedback sugerido",
        "manager_review_required": True,
    }

    assert AiFeedbackAnalysisService.validate_ai_json(payload)["summary"] == "Resumo"


def test_ai_json_validation_rejects_invalid_alert_severity():
    payload = {
        "employee_id": "1",
        "summary": "Resumo",
        "strengths": [],
        "attention_points": [],
        "recurring_themes": [],
        "qualitative_alerts": [{"type": "X", "description": "Y", "severity": "CRITICAL"}],
        "suggested_feedback": "Feedback",
    }

    with pytest.raises(ValueError, match="Alerta qualitativo invalido"):
        AiFeedbackAnalysisService.validate_ai_json(payload)


def test_ai_json_extraction_accepts_markdown_wrapper():
    raw = '```json\n{"employee_id":"1","summary":"ok"}\n```'
    assert AiFeedbackAnalysisService._extract_json(raw) == '{"employee_id":"1","summary":"ok"}'


def test_ai_error_message_masks_api_key():
    message = AiFeedbackAnalysisService._safe_error_message(Exception("url https://x?key=SECRET123 more"))
    assert "SECRET123" not in message
    assert "key=***" in message


def test_ai_fallback_uses_competency_scores():
    summary = AiFeedbackAnalysisService._score_based_summary(
        SimpleNamespace(name="Ana"),
        3,
        82.5,
        {"teamwork_score": 90, "communication_score": 62},
    )

    assert "82.5" in summary
    assert "Trabalho em equipe" in summary
    assert "Comunicacao" in summary


def test_ai_prompt_asks_to_use_numeric_360_when_comments_are_missing():
    class EmptyQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return []

    service = AiFeedbackAnalysisService(db=SimpleNamespace(query=lambda *_args, **_kwargs: EmptyQuery()))
    prompt = service.build_prompt(
        SimpleNamespace(id=1),
        SimpleNamespace(id=10, name="Ana", department="Operacoes", position="Analista"),
    )

    assert "notas por competencia" in prompt
    assert "review_360_numeric_summary" in prompt
    assert "Nao diga que a analise esta prejudicada" in prompt
