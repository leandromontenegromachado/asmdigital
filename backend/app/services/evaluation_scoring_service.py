from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import union_all

from app.models import (
    AuditLog,
    Employee,
    EvaluationAlert,
    EvaluationCycle,
    EvaluationScore,
    PerformanceIndicator,
    PotentialScore,
    Review360,
)


BEHAVIOR_WEIGHTS = {
    "MANAGER": 3.0,
    "PEER": 1.0,
    "INTERNAL_CLIENT": 1.0,
    "SELF": 0.0,
}

CATEGORY_DESCRIPTIONS = {
    "DESTAQUE": "Alta entrega, alto reconhecimento e forte impacto.",
    "MUITO_BOM": "Performance consistente e acima do esperado.",
    "BOM": "Entrega adequada e consistente.",
    "EM_DESENVOLVIMENTO": "Precisa de acompanhamento e evolucao.",
    "ATENCAO": "Requer plano de melhoria ou analise da gestao.",
}

NINE_BOX_DESCRIPTIONS = {
    "ALTO_ALTO": "Talento estrategico.",
    "ALTO_MEDIO": "Forte entregador.",
    "ALTO_BAIXO": "Especialista solido.",
    "MEDIO_ALTO": "Potencial em aceleracao.",
    "MEDIO_MEDIO": "Colaborador em crescimento.",
    "MEDIO_BAIXO": "Colaborador estavel.",
    "BAIXO_ALTO": "Potencial nao convertido.",
    "BAIXO_MEDIO": "Precisa de acompanhamento.",
    "BAIXO_BAIXO": "Atencao.",
}


@dataclass
class CalculationSummary:
    processed: int
    incomplete: int
    alerts_generated: int


class EvaluationScoringService:
    def __init__(self, db: Session, actor_id: int | None = None):
        self.db = db
        self.actor_id = actor_id

    @staticmethod
    def normalize_score(value: float | None) -> float | None:
        if value is None:
            return None
        return max(0.0, min(100.0, float(value)))

    @staticmethod
    def calculate_performance_score(rpm: float | None, ihpe: float | None) -> float | None:
        available = [score for score in (rpm, ihpe) if score is not None]
        if not available:
            return None
        return round(sum(available) / len(available), 2)

    @staticmethod
    def calculate_weighted_behavior_score(scores: dict[str, float | None]) -> float | None:
        available = [
            (relation, score, BEHAVIOR_WEIGHTS[relation])
            for relation, score in scores.items()
            if score is not None and BEHAVIOR_WEIGHTS[relation] > 0
        ]
        if not available:
            return None
        total_weight = sum(weight for _, _, weight in available)
        value = sum(score * (weight / total_weight) for _, score, weight in available)
        return round(value, 2)

    @staticmethod
    def calculate_final_score(
        performance_score: float | None,
        behavior_score: float | None,
        potential_score: float | None,
        performance_weight: float = 0.10,
        behavior_weight: float = 0.45,
        potential_weight: float = 0.45,
    ) -> float | None:
        available = [
            (performance_score, performance_weight),
            (behavior_score, behavior_weight),
            (potential_score, potential_weight),
        ]
        available = [(score, weight) for score, weight in available if score is not None and weight > 0]
        if not available:
            return None
        total_weight = sum(weight for _, weight in available)
        return round(sum(score * (weight / total_weight) for score, weight in available), 2)

    @staticmethod
    def classify_final_score(score: float) -> str:
        if score >= 90:
            return "DESTAQUE"
        if score >= 80:
            return "MUITO_BOM"
        if score >= 70:
            return "BOM"
        if score >= 60:
            return "EM_DESENVOLVIMENTO"
        return "ATENCAO"

    @staticmethod
    def classify_level(score: float) -> str:
        if score >= 80:
            return "ALTO"
        if score >= 60:
            return "MEDIO"
        return "BAIXO"

    @classmethod
    def calculate_nine_box(cls, performance_score: float, potential_score: float) -> str:
        return f"{cls.classify_level(performance_score)}_{cls.classify_level(potential_score)}"

    @staticmethod
    def generate_alert_specs(
        performance_score: float | None,
        behavior_score: float | None,
        manager_score: float | None,
        peer_score: float | None,
        missing_data: bool,
    ) -> list[tuple[str, str, str]]:
        alerts: list[tuple[str, str, str]] = []
        if missing_data:
            alerts.append((
                "MISSING_DATA",
                "Dados incompletos para calculo confiavel da avaliacao.",
                "HIGH",
            ))
        if performance_score is not None and behavior_score is not None:
            if performance_score >= 85 and behavior_score < 70:
                alerts.append((
                    "HIGH_PERFORMANCE_LOW_BEHAVIOR",
                    "Alta entrega objetiva, mas comportamento abaixo do esperado. Recomenda-se analise qualitativa dos feedbacks.",
                    "MEDIUM",
                ))
            if performance_score < 70 and behavior_score >= 85:
                alerts.append((
                    "LOW_PERFORMANCE_HIGH_BEHAVIOR",
                    "Boa avaliacao comportamental, mas produtividade abaixo do esperado. Recomenda-se avaliar necessidade de apoio, treinamento ou revisao de funcao.",
                    "MEDIUM",
                ))
        if manager_score is not None and peer_score is not None and abs(manager_score - peer_score) >= 20:
            alerts.append((
                "MANAGER_PEER_DIVERGENCE",
                "Ha divergencia relevante entre a avaliacao do gestor e a avaliacao dos pares. Recomenda-se analise na calibracao.",
                "HIGH",
            ))
        return alerts

    def calculate_cycle(self, cycle: EvaluationCycle) -> CalculationSummary:
        employee_ids_query = union_all(
            self.db.query(Review360.evaluated_id.label("employee_id")).filter(Review360.cycle_id == cycle.id),
            self.db.query(PerformanceIndicator.employee_id.label("employee_id")).filter(PerformanceIndicator.cycle_id == cycle.id),
            self.db.query(PotentialScore.employee_id.label("employee_id")).filter(PotentialScore.cycle_id == cycle.id),
        ).subquery()
        employees = (
            self.db.query(Employee)
            .join(employee_ids_query, employee_ids_query.c.employee_id == Employee.id)
            .filter(Employee.active.is_(True))
            .distinct()
            .order_by(Employee.name.asc())
            .all()
        )
        self.db.query(EvaluationScore).filter(
            EvaluationScore.cycle_id == cycle.id,
            ~EvaluationScore.employee_id.in_(self.db.query(employee_ids_query.c.employee_id)),
        ).delete(synchronize_session=False)
        self.db.query(EvaluationAlert).filter(EvaluationAlert.cycle_id == cycle.id, EvaluationAlert.resolved_at.is_(None)).delete()

        processed = 0
        incomplete = 0
        alerts_generated = 0

        for employee in employees:
            summary = self._calculate_employee(cycle, employee)
            processed += 1
            if summary["incomplete"]:
                incomplete += 1
            alerts_generated += summary["alerts"]

        self._audit("CALCULATE_SCORES", "evaluation_cycles", cycle.id, None, {
            "processed": processed,
            "incomplete": incomplete,
            "alerts_generated": alerts_generated,
        })
        self.db.commit()
        return CalculationSummary(processed=processed, incomplete=incomplete, alerts_generated=alerts_generated)

    def _calculate_employee(self, cycle: EvaluationCycle, employee: Employee) -> dict[str, int | bool]:
        indicator = (
            self.db.query(PerformanceIndicator)
            .filter(PerformanceIndicator.cycle_id == cycle.id, PerformanceIndicator.employee_id == employee.id)
            .first()
        )
        potential = (
            self.db.query(PotentialScore)
            .filter(PotentialScore.cycle_id == cycle.id, PotentialScore.employee_id == employee.id)
            .first()
        )
        review_scores = self._review_averages(cycle.id, employee.id)

        rpm = indicator.rpm_normalized if indicator else None
        ihpe = indicator.ihpe_normalized if indicator else None
        performance_score = self.calculate_performance_score(rpm, ihpe)
        behavior_score = self._calculate_behavior_score_from_reviews(cycle.id, employee.id)
        potential_score = potential.score if potential else None

        missing_data = (
            rpm is None
            or ihpe is None
            or behavior_score is None
            or potential_score is None
        )

        score_row = (
            self.db.query(EvaluationScore)
            .filter(EvaluationScore.cycle_id == cycle.id, EvaluationScore.employee_id == employee.id)
            .first()
        )
        if not score_row:
            score_row = EvaluationScore(cycle_id=cycle.id, employee_id=employee.id)
            self.db.add(score_row)

        score_row.performance_score = performance_score
        score_row.behavior_score = behavior_score
        score_row.potential_score = potential_score

        can_calculate_final = behavior_score is not None and potential_score is not None
        if can_calculate_final:
            final_score = self.calculate_final_score(
                performance_score,
                behavior_score,
                potential_score,
                cycle.performance_weight,
                cycle.behavior_weight,
                cycle.potential_weight,
            )
            if final_score is None:
                return {"incomplete": missing_data, "alerts": 0}
            category = self.classify_final_score(final_score)
            score_row.preliminary_final_score = final_score
            score_row.suggested_category = category
            if not score_row.final_category or (not score_row.calibrated_at and not score_row.calibration_justification):
                score_row.final_category = category
            if performance_score is not None:
                score_row.nine_box_position = self.calculate_nine_box(performance_score, potential_score)
        else:
            score_row.preliminary_final_score = None
            score_row.suggested_category = None
            if not score_row.calibrated_at and not score_row.calibration_justification:
                score_row.final_category = None
            score_row.nine_box_position = None

        alerts = self.generate_alert_specs(
            performance_score,
            behavior_score,
            review_scores.get("MANAGER"),
            review_scores.get("PEER"),
            missing_data,
        )
        for alert_type, message, severity in alerts:
            self.db.add(EvaluationAlert(
                cycle_id=cycle.id,
                employee_id=employee.id,
                alert_type=alert_type,
                message=message,
                severity=severity,
            ))

        return {"incomplete": missing_data, "alerts": len(alerts)}

    def _review_averages(self, cycle_id: int, employee_id: int) -> dict[str, float | None]:
        result: dict[str, float | None] = {key: None for key in BEHAVIOR_WEIGHTS}
        for relation in BEHAVIOR_WEIGHTS:
            rows = (
                self.db.query(Review360.score, Review360.general_score, Review360.evaluator_id, Review360.evaluator_name, Review360.evaluated_name)
                .filter(
                    Review360.cycle_id == cycle_id,
                    Review360.evaluated_id == employee_id,
                    Review360.relation_type == relation,
                )
                .all()
            )
            values = [
                (row.general_score if row.general_score is not None else row.score)
                for row in rows
                if not self._is_self_review(row.evaluator_id, employee_id, row.evaluator_name, row.evaluated_name)
            ]
            values = [value for value in values if value is not None]
            if values:
                result[relation] = round(sum(values) / len(values), 2)
        return result

    def _calculate_behavior_score_from_reviews(self, cycle_id: int, employee_id: int) -> float | None:
        rows = (
            self.db.query(
                Review360.score,
                Review360.general_score,
                Review360.relation_type,
                Review360.evaluator_id,
                Review360.evaluator_name,
                Review360.evaluated_name,
            )
            .filter(Review360.cycle_id == cycle_id, Review360.evaluated_id == employee_id)
            .all()
        )
        weighted_total = 0.0
        total_weight = 0.0
        for row in rows:
            if self._is_self_review(row.evaluator_id, employee_id, row.evaluator_name, row.evaluated_name):
                continue
            score = row.general_score if row.general_score is not None else row.score
            if score is None:
                continue
            weight = 3.0 if row.relation_type == "MANAGER" else 1.0
            if row.relation_type == "SELF":
                continue
            weighted_total += score * weight
            total_weight += weight
        if total_weight == 0:
            return None
        return round(weighted_total / total_weight, 2)

    @staticmethod
    def _is_self_review(evaluator_id: int | None, employee_id: int, evaluator_name: str | None, evaluated_name: str | None) -> bool:
        if evaluator_id and evaluator_id == employee_id:
            return True
        if evaluator_name and evaluated_name:
            return evaluator_name.strip().casefold() == evaluated_name.strip().casefold()
        return False

    def calibrate(
        self,
        cycle: EvaluationCycle,
        score: EvaluationScore,
        final_category: str,
        justification: str | None,
    ) -> None:
        if cycle.status == "FINALIZADO":
            raise ValueError("Ciclo finalizado nao permite calibracao")
        if score.suggested_category and final_category != score.suggested_category and not (justification or "").strip():
            raise ValueError("Justificativa obrigatoria quando a categoria final difere da sugerida")

        old_value = {
            "final_category": score.final_category,
            "calibration_justification": score.calibration_justification,
        }
        score.final_category = final_category
        score.calibration_justification = justification
        score.calibrated_by = self.actor_id
        score.calibrated_at = datetime.utcnow()
        self._audit("CALIBRATE_CATEGORY", "evaluation_scores", score.id, old_value, {
            "suggested_category": score.suggested_category,
            "final_category": final_category,
            "calibration_justification": justification,
            "preliminary_final_score": score.preliminary_final_score,
        })

    def _audit(self, action: str, entity_type: str, entity_id: int | None, old_value, new_value) -> None:
        self.db.add(AuditLog(
            user_id=self.actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
        ))
