from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.evaluation_scoring_service import EvaluationScoringService


def test_calculate_performance_score():
    assert EvaluationScoringService.calculate_performance_score(80, 90) == 85
    assert EvaluationScoringService.calculate_performance_score(None, 90) == 90
    assert EvaluationScoringService.calculate_performance_score(None, None) is None


def test_behavior_score_with_all_reviewers():
    score = EvaluationScoringService.calculate_weighted_behavior_score({
        "MANAGER": 90,
        "PEER": 80,
        "INTERNAL_CLIENT": 70,
        "SELF": 100,
    })
    assert score == 84


def test_behavior_score_rebalances_missing_reviewers():
    score = EvaluationScoringService.calculate_weighted_behavior_score({
        "MANAGER": 90,
        "PEER": 80,
        "INTERNAL_CLIENT": None,
        "SELF": 100,
    })
    assert score == 87.5


def test_calculate_final_score():
    assert EvaluationScoringService.calculate_final_score(100, 50, 50) == 55
    assert EvaluationScoringService.calculate_final_score(None, 80, 90) == 85
    assert EvaluationScoringService.calculate_final_score(80, 90, 70, 0.45, 0.35, 0.20) == 81.5


@pytest.mark.parametrize(
    ("score", "category"),
    [
        (95, "DESTAQUE"),
        (85, "MUITO_BOM"),
        (75, "BOM"),
        (65, "EM_DESENVOLVIMENTO"),
        (55, "ATENCAO"),
    ],
)
def test_classify_final_score(score, category):
    assert EvaluationScoringService.classify_final_score(score) == category


@pytest.mark.parametrize(
    ("performance", "potential", "position"),
    [
        (85, 90, "ALTO_ALTO"),
        (85, 70, "ALTO_MEDIO"),
        (70, 55, "MEDIO_BAIXO"),
        (55, 90, "BAIXO_ALTO"),
    ],
)
def test_calculate_nine_box(performance, potential, position):
    assert EvaluationScoringService.calculate_nine_box(performance, potential) == position


def test_alert_high_performance_low_behavior():
    alerts = EvaluationScoringService.generate_alert_specs(90, 60, 80, 80, False)
    assert alerts[0][0] == "HIGH_PERFORMANCE_LOW_BEHAVIOR"


def test_alert_low_performance_high_behavior():
    alerts = EvaluationScoringService.generate_alert_specs(60, 90, 80, 80, False)
    assert alerts[0][0] == "LOW_PERFORMANCE_HIGH_BEHAVIOR"


def test_alert_manager_peer_divergence():
    alerts = EvaluationScoringService.generate_alert_specs(80, 80, 95, 70, False)
    assert alerts[0][0] == "MANAGER_PEER_DIVERGENCE"


def test_calibration_requires_justification_when_category_changes():
    db = MagicMock()
    service = EvaluationScoringService(db, actor_id=1)
    cycle = SimpleNamespace(status="EM_CALIBRACAO")
    score = SimpleNamespace(suggested_category="BOM", final_category="BOM", calibration_justification=None)

    with pytest.raises(ValueError):
        service.calibrate(cycle, score, "DESTAQUE", None)


def test_calibration_blocks_finalized_cycle():
    db = MagicMock()
    service = EvaluationScoringService(db, actor_id=1)
    cycle = SimpleNamespace(status="FINALIZADO")
    score = SimpleNamespace(suggested_category="BOM", final_category="BOM", calibration_justification=None)

    with pytest.raises(ValueError):
        service.calibrate(cycle, score, "BOM", None)
