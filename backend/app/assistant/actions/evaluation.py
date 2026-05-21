from __future__ import annotations

import unicodedata
from collections import defaultdict
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.assistant.actions.base import ActionResult
from app.assistant.schemas import AssistantPlan
from app.models import (
    AiFeedbackAnalysis,
    Employee,
    EvaluationAlert,
    EvaluationCycle,
    EvaluationScore,
    PotentialScore,
    Review360,
    User,
)


class EvaluationAction:
    domain = "evaluation"

    def preview(self, db: Session, plan: AssistantPlan, user: User | None) -> dict[str, Any]:
        params = plan.extracted_params or {}
        return {
            "title": "Avaliacao 360",
            "domain": "evaluation",
            "action": "status",
            "params": params,
            "missing_params": plan.missing_params,
            "impact": "Consulta somente leitura dos ciclos, notas, feedbacks e analises IA da Avaliacao 360.",
        }

    def execute(self, db: Session, plan: AssistantPlan, user: User | None) -> ActionResult:
        params = plan.extracted_params or {}
        employee_name = str(params.get("employee_name") or params.get("employee") or params.get("name") or "").strip()
        if not employee_name:
            return self._list_cycles(db)

        employee = self._find_employee(db, employee_name)
        review_name = None if employee else self._find_review_name(db, employee_name)
        if not employee and not review_name:
            return ActionResult(
                message=f"Nao encontrei funcionario ou avaliacao 360 para '{employee_name}'.",
                data={"query": employee_name},
                success=False,
                errors=["employee_not_found"],
            )

        cycle = self._latest_cycle_for_employee(db, employee, review_name)
        if not cycle:
            display_name = employee.name if employee else review_name
            return ActionResult(
                message=f"Encontrei {display_name}, mas nao encontrei dados de Avaliacao 360 vinculados.",
                data={"employee": self._employee_data(employee, review_name)},
                success=False,
                errors=["evaluation_not_found"],
            )

        score = self._score(db, cycle.id, employee.id) if employee else None
        potential = self._potential(db, cycle.id, employee.id) if employee else None
        ai = self._ai_feedback(db, cycle.id, employee.id) if employee else None
        alerts = self._alerts(db, cycle.id, employee.id) if employee else []
        reviews = self._reviews(db, cycle.id, employee, review_name)
        review_summary = self._review_summary(reviews)

        data = {
            "employee": self._employee_data(employee, review_name),
            "cycle": self._cycle_data(cycle),
            "score": self._score_data(score),
            "potential": self._potential_data(potential),
            "reviews": review_summary,
            "ai_feedback": self._ai_data(ai),
            "alerts": [self._alert_data(row) for row in alerts],
        }
        return ActionResult(message=self._message(data), data=data)

    def _list_cycles(self, db: Session) -> ActionResult:
        cycles = db.query(EvaluationCycle).order_by(EvaluationCycle.start_date.desc(), EvaluationCycle.id.desc()).limit(10).all()
        items = [self._cycle_data(cycle) for cycle in cycles]
        if not items:
            return ActionResult(message="Nao encontrei ciclos de Avaliacao 360 cadastrados.", data={"total": 0, "items": []})
        lines = [f"Encontrei {len(items)} ciclo(s) de Avaliacao 360."]
        for item in items[:5]:
            lines.append(f"- {item['name']} ({item['status']})")
        return ActionResult(message="\n".join(lines), data={"total": len(items), "items": items})

    def _find_employee(self, db: Session, name: str) -> Employee | None:
        normalized_query = _normalize(name)
        if not normalized_query:
            return None
        employees = db.query(Employee).all()
        best: tuple[float, Employee] | None = None
        for employee in employees:
            score = _name_score(normalized_query, employee.name or "")
            if score >= 0.55 and (best is None or score > best[0]):
                best = (score, employee)
        return best[1] if best else None

    def _find_review_name(self, db: Session, name: str) -> str | None:
        normalized_query = _normalize(name)
        rows = db.query(Review360.evaluated_name).filter(Review360.evaluated_name.isnot(None)).distinct().all()
        best: tuple[float, str] | None = None
        for row in rows:
            value = row[0]
            score = _name_score(normalized_query, value or "")
            if score >= 0.55 and (best is None or score > best[0]):
                best = (score, value)
        return best[1] if best else None

    def _latest_cycle_for_employee(self, db: Session, employee: Employee | None, review_name: str | None) -> EvaluationCycle | None:
        cycle_ids: list[int] = []
        if employee:
            for model in (EvaluationScore, AiFeedbackAnalysis, PotentialScore, EvaluationAlert):
                rows = db.query(model.cycle_id).filter(model.employee_id == employee.id).all()
                cycle_ids.extend([row[0] for row in rows])
            review_rows = db.query(Review360.cycle_id).filter(
                or_(Review360.evaluated_id == employee.id, Review360.evaluated_name.ilike(f"%{employee.name}%"))
            ).all()
            cycle_ids.extend([row[0] for row in review_rows])
        if review_name:
            review_rows = db.query(Review360.cycle_id).filter(Review360.evaluated_name.ilike(f"%{review_name}%")).all()
            cycle_ids.extend([row[0] for row in review_rows])

        if not cycle_ids:
            return None
        return (
            db.query(EvaluationCycle)
            .filter(EvaluationCycle.id.in_(set(cycle_ids)))
            .order_by(EvaluationCycle.start_date.desc(), EvaluationCycle.id.desc())
            .first()
        )

    def _score(self, db: Session, cycle_id: int, employee_id: int) -> EvaluationScore | None:
        return db.query(EvaluationScore).filter(EvaluationScore.cycle_id == cycle_id, EvaluationScore.employee_id == employee_id).first()

    def _potential(self, db: Session, cycle_id: int, employee_id: int) -> PotentialScore | None:
        return db.query(PotentialScore).filter(PotentialScore.cycle_id == cycle_id, PotentialScore.employee_id == employee_id).first()

    def _ai_feedback(self, db: Session, cycle_id: int, employee_id: int) -> AiFeedbackAnalysis | None:
        return db.query(AiFeedbackAnalysis).filter(AiFeedbackAnalysis.cycle_id == cycle_id, AiFeedbackAnalysis.employee_id == employee_id).first()

    def _alerts(self, db: Session, cycle_id: int, employee_id: int) -> list[EvaluationAlert]:
        return (
            db.query(EvaluationAlert)
            .filter(EvaluationAlert.cycle_id == cycle_id, EvaluationAlert.employee_id == employee_id)
            .order_by(EvaluationAlert.created_at.desc(), EvaluationAlert.id.desc())
            .limit(10)
            .all()
        )

    def _reviews(self, db: Session, cycle_id: int, employee: Employee | None, review_name: str | None) -> list[Review360]:
        filters = []
        if employee:
            filters.append(Review360.evaluated_id == employee.id)
            filters.append(Review360.evaluated_name.ilike(f"%{employee.name}%"))
        if review_name:
            filters.append(Review360.evaluated_name.ilike(f"%{review_name}%"))
        if not filters:
            return []
        return db.query(Review360).filter(Review360.cycle_id == cycle_id, or_(*filters)).all()

    def _review_summary(self, reviews: list[Review360]) -> dict[str, Any]:
        by_relation: dict[str, list[float]] = defaultdict(list)
        samples: list[dict[str, Any]] = []
        for review in reviews:
            relation = review.relation_type or "nao_informado"
            score = self._review_score(review)
            if score is not None:
                by_relation[relation].append(score)
            if len(samples) < 5:
                samples.append(
                    {
                        "relation_type": relation,
                        "score": score,
                        "strengths_comment": review.strengths_comment,
                        "improvement_comment": review.improvement_comment,
                        "general_comment": review.general_comment or review.comment,
                    }
                )
        averages = {
            relation: round(sum(values) / len(values), 2)
            for relation, values in by_relation.items()
            if values
        }
        all_scores = [score for values in by_relation.values() for score in values]
        return {
            "total": len(reviews),
            "average_score": round(sum(all_scores) / len(all_scores), 2) if all_scores else None,
            "averages_by_relation": averages,
            "samples": samples,
        }

    def _review_score(self, review: Review360) -> float | None:
        if review.score is not None:
            return float(review.score)
        values = [
            review.general_score,
            review.communication_score,
            review.teamwork_score,
            review.commitment_score,
            review.autonomy_score,
            review.quality_score,
            review.problem_solving_score,
        ]
        numeric = [float(value) for value in values if value is not None]
        return round(sum(numeric) / len(numeric), 2) if numeric else None

    def _message(self, data: dict[str, Any]) -> str:
        employee = data["employee"]
        cycle = data["cycle"]
        score = data.get("score") or {}
        reviews = data.get("reviews") or {}
        ai = data.get("ai_feedback") or {}
        alerts = data.get("alerts") or []

        lines = [f"Avaliacao 360 de {employee['name']} no ciclo {cycle['name']} ({cycle['status']})."]
        if score:
            category = score.get("final_category") or score.get("suggested_category") or "sem categoria"
            final_score = _format_number(score.get("preliminary_final_score"))
            parts = [f"Resultado: {category}"]
            if final_score:
                parts.append(f"nota final {final_score}")
            if score.get("nine_box_position"):
                parts.append(f"nine box {score['nine_box_position']}")
            lines.append("; ".join(parts) + ".")
            detail = []
            if score.get("performance_score") is not None:
                detail.append(f"performance {_format_number(score['performance_score'])}")
            if score.get("behavior_score") is not None:
                detail.append(f"comportamento {_format_number(score['behavior_score'])}")
            if score.get("potential_score") is not None:
                detail.append(f"potencial {_format_number(score['potential_score'])}")
            if detail:
                lines.append("Componentes: " + ", ".join(detail) + ".")
        if reviews.get("total"):
            average = _format_number(reviews.get("average_score")) or "sem media"
            lines.append(f"Feedbacks 360: {reviews['total']} resposta(s), media {average}.")
            if reviews.get("averages_by_relation"):
                relation_parts = [f"{key}: {_format_number(value)}" for key, value in reviews["averages_by_relation"].items()]
                lines.append("Por relacao: " + ", ".join(relation_parts) + ".")
        if ai.get("summary"):
            lines.append(f"Resumo IA: {ai['summary']}")
        if ai.get("suggested_feedback"):
            lines.append(f"Feedback sugerido: {ai['suggested_feedback']}")
        if alerts:
            lines.append(f"Alertas: {len(alerts)} registro(s). Principal: {alerts[0]['message']}")
        if len(lines) == 1:
            lines.append("Ha dados vinculados, mas ainda nao ha nota, feedback IA ou respostas 360 consolidadas.")
        return "\n".join(lines)

    def _employee_data(self, employee: Employee | None, fallback_name: str | None) -> dict[str, Any]:
        if not employee:
            return {"id": None, "name": fallback_name, "department": None, "position": None}
        return {
            "id": employee.id,
            "name": employee.name,
            "email": employee.email,
            "department": employee.department or employee.setor,
            "position": employee.position or employee.cargo,
            "active": employee.active,
        }

    def _cycle_data(self, cycle: EvaluationCycle) -> dict[str, Any]:
        return {
            "id": cycle.id,
            "name": cycle.name,
            "status": cycle.status,
            "start_date": _date_value(cycle.start_date),
            "end_date": _date_value(cycle.end_date),
        }

    def _score_data(self, score: EvaluationScore | None) -> dict[str, Any] | None:
        if not score:
            return None
        return {
            "performance_score": score.performance_score,
            "behavior_score": score.behavior_score,
            "potential_score": score.potential_score,
            "preliminary_final_score": score.preliminary_final_score,
            "suggested_category": score.suggested_category,
            "final_category": score.final_category,
            "nine_box_position": score.nine_box_position,
            "calibration_justification": score.calibration_justification,
        }

    def _potential_data(self, potential: PotentialScore | None) -> dict[str, Any] | None:
        if not potential:
            return None
        return {"score": potential.score, "comment": potential.comment}

    def _ai_data(self, ai: AiFeedbackAnalysis | None) -> dict[str, Any] | None:
        if not ai:
            return None
        return {
            "status": ai.status,
            "summary": ai.summary,
            "strengths": ai.strengths_json,
            "attention_points": ai.attention_points_json,
            "recurring_themes": ai.recurring_themes_json,
            "qualitative_alerts": ai.qualitative_alerts_json,
            "suggested_feedback": ai.suggested_feedback,
            "model_used": ai.model_used,
            "error_message": ai.error_message,
        }

    def _alert_data(self, alert: EvaluationAlert) -> dict[str, Any]:
        return {
            "id": alert.id,
            "alert_type": alert.alert_type,
            "message": alert.message,
            "severity": alert.severity,
            "created_at": _date_value(alert.created_at),
            "resolved_at": _date_value(alert.resolved_at),
        }


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().strip().split())


def _name_score(query: str, candidate: str) -> float:
    normalized = _normalize(candidate)
    if not query or not normalized:
        return 0.0
    if query == normalized:
        return 1.0
    if query in normalized or normalized in query:
        return 0.92
    query_tokens = set(query.split())
    candidate_tokens = set(normalized.split())
    if not query_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(candidate_tokens)) / len(query_tokens)
    return overlap


def _format_number(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{float(value):.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def _date_value(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
