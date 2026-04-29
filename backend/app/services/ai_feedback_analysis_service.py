import json
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AiFeedbackAnalysis,
    AuditLog,
    Employee,
    EmployeeRhData,
    EvaluationCycle,
    EvaluationScore,
    PerformanceIndicator,
    PotentialScore,
    Review360,
)
from app.services.evaluation_scoring_service import BEHAVIOR_WEIGHTS


RETRYABLE_AI_STATUS_CODES = {429, 500, 502, 503, 504}
AI_RETRY_DELAYS_SECONDS = [5.0, 15.0, 30.0]
AI_CYCLE_DELAY_SECONDS = 6.0


class AiFeedbackAnalysisService:
    def __init__(self, db: Session, actor_id: int | None = None):
        self.db = db
        self.actor_id = actor_id

    def build_prompt(self, cycle: EvaluationCycle, employee: Employee) -> str:
        all_reviews = self._raw_reviews(cycle.id, employee.id)
        reviews = self._filter_self_reviews(all_reviews, employee.id)
        competency_averages = self._competency_averages(reviews)
        relation_averages = self._relation_averages(reviews)
        general_values = [row.general_score or row.score for row in reviews if row.general_score is not None or row.score is not None]
        indicator = self._indicator(cycle.id, employee.id)
        potential = self._potential(cycle.id, employee.id)
        score = self._score(cycle.id, employee.id)
        rh = self._rh_data(cycle.id, employee.id)
        comments = {
            "strengths": [row.strengths_comment for row in reviews if row.strengths_comment],
            "improvements": [row.improvement_comment for row in reviews if row.improvement_comment],
            "general": [row.general_comment or row.comment for row in reviews if row.general_comment or row.comment],
        }
        return json.dumps({
            "instruction": (
                "Analise a avaliacao anual de desempenho da ASM de forma gerencial, detalhada, objetiva e explicavel. "
                "Use comentarios textuais quando existirem, mas se houver poucos comentarios, use principalmente as notas por competencia, medias, dispersao e diferencas entre dimensoes. "
                "Compare competencias mais fortes e mais fracas, identifique padroes, possiveis riscos e pontos para calibracao. "
                "Desconsidere autoavaliacoes. Nao revele nem sugira o nome de quem avaliou. "
                "Trate o texto final como feedback da chefia, consolidado a partir das evidencias, sem expor avaliadores. "
                "Nao diga que a analise esta prejudicada apenas por falta de comentarios se houver notas numericas suficientes. "
                "Nao decida nota, categoria, promocao ou resultado final. "
                "Nao mencione que esta sem dados se houver avaliacoes numericas. "
                "Retorne apenas JSON valido no schema solicitado, em portugues do Brasil."
            ),
            "methodology_context": {
                "process": "Avaliacao anual de desempenho da ASM para apoiar promocao por merito.",
                "manager_weight": "Avaliacao do gestor tem peso 3x em relacao aos pares no calculo 360.",
                "self_review_rule": "Autoavaliacoes devem ser desconsideradas no calculo e no texto de feedback.",
                "merit_rules": [
                    "Promocao por merito ocorre apenas uma vez a cada 12 meses.",
                    "Funcionarios de nivel 1 concorrem em verba separada e precisam pelo menos desempenho Muito Bom.",
                    "Teto de carreira da empresa: nivel 24.",
                ],
                "tie_breakers": [
                    "Responsabilidade e comprometimento.",
                    "Produtividade, com apoio de RPM e IHPE quando disponiveis.",
                    "Entregas de valor, qualidade e consistencia das entregas.",
                ],
                "rpm_rule": "RPM% deve representar horas em projetos dividido por horas totais, excluindo atividades genericas e treinamento.",
                "ihpe_rule": "IHPE% deve ser recalculado por mes como horas em entregaveis dividido por horas trabalhadas, depois media dos meses apurados.",
                "decision_boundary": "A IA apoia a sintese qualitativa. A decisao final e a indicacao de promocao sao humanas e auditaveis.",
            },
            "analysis_depth_required": {
                "summary": "Escreva 1 paragrafo com leitura consolidada do perfil percebido na 360.",
                "strengths": "Liste de 3 a 5 pontos fortes baseados nas maiores medias e padroes das avaliacoes.",
                "attention_points": "Liste de 3 a 5 pontos de atencao baseados nas menores medias, dispersoes ou inconsistencias.",
                "recurring_themes": "Liste padroes objetivos observados nas notas, competencias e comentarios, sem identificar avaliadores.",
                "qualitative_alerts": "Inclua alertas apenas se houver risco, divergencia ou baixa consistencia perceptivel.",
                "suggested_feedback": "Escreva um paragrafo unico de feedback como se fosse comentario da chefia, seguido de um plano objetivo para os proximos 6 meses.",
            },
            "schema": {
                "employee_id": "string",
                "summary": "string",
                "strengths": ["string"],
                "attention_points": ["string"],
                "recurring_themes": ["string"],
                "qualitative_alerts": [{"type": "string", "description": "string", "severity": "LOW|MEDIUM|HIGH"}],
                "suggested_feedback": "string",
                "manager_review_required": True,
            },
            "employee": {
                "employee_id": str(employee.id),
                "name": employee.name,
                "department": employee.department,
                "position": employee.position,
            },
            "operational_and_hr_context": {
                "rpm_percent": indicator.rpm_normalized if indicator else None,
                "ihpe_percent": indicator.ihpe_normalized if indicator else None,
                "performance_score": score.performance_score if score else None,
                "manager_score": potential.score if potential else None,
                "preliminary_final_score": score.preliminary_final_score if score else None,
                "career_level_anc": rh.career_level if rh else None,
                "last_merit_date": rh.last_merit_date.isoformat() if rh and rh.last_merit_date else None,
                "admission_date": rh.admission_date.isoformat() if rh and rh.admission_date else None,
                "level_one_separate_budget": rh.is_level_one_separate_budget if rh else None,
                "eligible_for_merit": rh.eligible_for_merit if rh else None,
                "eligibility_reason": rh.eligibility_reason if rh else None,
            },
            "review_360_numeric_summary": {
                "review_count": len(reviews),
                "excluded_self_review_count": len(all_reviews) - len(reviews),
                "general_average": round(sum(general_values) / len(general_values), 2) if general_values else None,
                "general_min": min(general_values) if general_values else None,
                "general_max": max(general_values) if general_values else None,
                "competency_averages": competency_averages,
                "reviewer_type_averages": relation_averages,
                "strongest_competencies": self._rank_competencies(competency_averages, reverse=True),
                "weakest_competencies": self._rank_competencies(competency_averages, reverse=False),
            },
            "review_360_items": [
                self._review_payload(row)
                for row in reviews[:40]
            ],
            "comments": comments,
        }, ensure_ascii=False)

    def run_analysis_for_cycle(self, cycle: EvaluationCycle) -> list[AiFeedbackAnalysis]:
        employees = (
            self.db.query(Employee)
            .join(Review360, Review360.evaluated_id == Employee.id)
            .filter(Review360.cycle_id == cycle.id)
            .distinct()
            .order_by(Employee.name.asc())
            .all()
        )
        results: list[AiFeedbackAnalysis] = []
        for employee in employees:
            results.append(self.run_analysis_for_employee(cycle, employee))
            time.sleep(AI_CYCLE_DELAY_SECONDS)
        return results

    def run_analysis_for_employee(self, cycle: EvaluationCycle, employee: Employee) -> AiFeedbackAnalysis:
        analysis = (
            self.db.query(AiFeedbackAnalysis)
            .filter(AiFeedbackAnalysis.cycle_id == cycle.id, AiFeedbackAnalysis.employee_id == employee.id)
            .first()
        )
        if not analysis:
            analysis = AiFeedbackAnalysis(cycle_id=cycle.id, employee_id=employee.id, status="PENDING")
            self.db.add(analysis)
            self.db.flush()

        prompt = self.build_prompt(cycle, employee)
        try:
            payload = self._call_ai(prompt, employee)
            validated = self.validate_ai_json(payload)
            analysis.status = "PROCESSED"
            analysis.summary = validated["summary"]
            analysis.strengths_json = validated["strengths"]
            analysis.attention_points_json = validated["attention_points"]
            analysis.recurring_themes_json = validated["recurring_themes"]
            analysis.qualitative_alerts_json = validated["qualitative_alerts"]
            analysis.suggested_feedback = validated["suggested_feedback"]
            analysis.raw_response_json = validated
            analysis.model_used = settings.fala_ai_gemini_model if settings.fala_ai_gemini_api_key else "deterministic-fallback"
            analysis.error_message = None
        except httpx.HTTPStatusError as exc:
            fallback = self._fallback_analysis(employee, cycle.id)
            status_code = exc.response.status_code
            self._apply_fallback(analysis, fallback, {"provider_error_status": status_code})
            if status_code == 429:
                analysis.error_message = "Aviso: a IA externa atingiu limite temporario de requisicoes (429). Foi exibida analise local de apoio com os dados disponiveis."
            else:
                analysis.error_message = f"Aviso: a IA externa ficou indisponivel temporariamente ({status_code}). Foi exibida analise local de apoio com os dados disponiveis."
        except httpx.TimeoutException:
            fallback = self._fallback_analysis(employee, cycle.id)
            self._apply_fallback(analysis, fallback, {"provider_error": "timeout"})
            analysis.error_message = (
                f"Aviso: a IA externa excedeu o tempo limite de {settings.fala_ai_gemini_timeout_seconds}s. "
                "Foi exibida analise local de apoio com os dados disponiveis."
            )
        except Exception as exc:
            analysis.status = "ERROR"
            analysis.error_message = self._safe_error_message(exc)

        self.db.add(AuditLog(
            user_id=self.actor_id,
            action="RUN_AI_FEEDBACK_ANALYSIS",
            entity_type="ai_feedback_analysis",
            entity_id=analysis.id,
            old_value=None,
            new_value={"cycle_id": cycle.id, "employee_id": employee.id, "status": analysis.status},
        ))
        return analysis

    @staticmethod
    def _apply_fallback(analysis: AiFeedbackAnalysis, fallback: dict[str, Any], metadata: dict[str, Any]) -> None:
        analysis.status = "PROCESSED"
        analysis.summary = fallback["summary"]
        analysis.strengths_json = fallback["strengths"]
        analysis.attention_points_json = fallback["attention_points"]
        analysis.recurring_themes_json = fallback["recurring_themes"]
        analysis.qualitative_alerts_json = fallback["qualitative_alerts"]
        analysis.suggested_feedback = fallback["suggested_feedback"]
        analysis.raw_response_json = {"fallback": fallback, **metadata}
        analysis.model_used = "deterministic-fallback"

    @staticmethod
    def validate_ai_json(payload: dict[str, Any]) -> dict[str, Any]:
        required = ["employee_id", "summary", "strengths", "attention_points", "recurring_themes", "qualitative_alerts", "suggested_feedback"]
        missing = [field for field in required if field not in payload]
        if missing:
            raise ValueError(f"JSON da IA sem campos obrigatorios: {', '.join(missing)}")
        for field in ["strengths", "attention_points", "recurring_themes", "qualitative_alerts"]:
            if not isinstance(payload[field], list):
                raise ValueError(f"Campo {field} precisa ser uma lista")
        for alert in payload["qualitative_alerts"]:
            if not isinstance(alert, dict) or alert.get("severity") not in {"LOW", "MEDIUM", "HIGH"}:
                raise ValueError("Alerta qualitativo invalido")
        if not isinstance(payload["summary"], str) or not isinstance(payload["suggested_feedback"], str):
            raise ValueError("Resumo e feedback sugerido precisam ser texto")
        return payload

    def _call_ai(self, prompt: str, employee: Employee) -> dict[str, Any]:
        if not settings.fala_ai_gemini_api_key:
            return self._fallback_analysis(employee)

        last_error: httpx.HTTPStatusError | None = None
        for attempt, delay in enumerate([0.0] + AI_RETRY_DELAYS_SECONDS, start=1):
            if delay:
                time.sleep(delay)
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{settings.fala_ai_gemini_model}:generateContent",
                headers={"x-goog-api-key": settings.fala_ai_gemini_api_key},
                json={
                    "system_instruction": {"parts": [{"text": "Retorne somente JSON valido. Nao defina nota, categoria ou decisao final."}]},
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 2500,
                        "responseMimeType": "application/json",
                    },
                },
                timeout=settings.fala_ai_gemini_timeout_seconds,
            )
            try:
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code not in RETRYABLE_AI_STATUS_CODES or attempt > len(AI_RETRY_DELAYS_SECONDS):
                    raise
        else:
            if last_error:
                raise last_error
            raise RuntimeError("Falha desconhecida ao chamar Gemini")
        data = response.json()
        text = (
            (data.get("candidates") or [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        return json.loads(self._extract_json(text))

    @staticmethod
    def _extract_json(text: str) -> str:
        value = (text or "").strip()
        if value.startswith("```"):
            value = value.strip("`").strip()
            if value.lower().startswith("json"):
                value = value[4:].strip()
        if value.startswith("{") and value.endswith("}"):
            return value
        start = value.find("{")
        end = value.rfind("}")
        if start >= 0 and end > start:
            return value[start:end + 1]
        return value

    def _fallback_analysis(self, employee: Employee, cycle_id: int | None = None) -> dict[str, Any]:
        reviews = self._reviews(cycle_id, employee.id) if cycle_id else self._reviews_for_employee(employee.id)
        competency_averages = self._competency_averages(reviews)
        relation_averages = self._relation_averages(reviews)
        indicator = self._indicator(cycle_id, employee.id) if cycle_id else None
        potential = self._potential(cycle_id, employee.id) if cycle_id else None
        score = self._score(cycle_id, employee.id) if cycle_id else None
        rh = self._rh_data(cycle_id, employee.id) if cycle_id else None
        general_values = [row.general_score or row.score for row in reviews if row.general_score is not None or row.score is not None]
        general_average = round(sum(general_values) / len(general_values), 2) if general_values else None
        strengths = self._collect_terms([row.strengths_comment for row in reviews])
        attention = self._collect_terms([row.improvement_comment for row in reviews])
        general = self._collect_terms([row.general_comment or row.comment for row in reviews])
        score_strengths = self._score_based_strengths(competency_averages)
        score_attention = self._score_based_attention_points(competency_averages)
        themes = self._score_based_themes(general_average, relation_averages)
        themes.extend(self._operational_themes(indicator, potential, score, rh))
        return {
            "employee_id": str(employee.id),
            "summary": self._score_based_summary(employee, len(reviews), general_average, competency_averages)
            + self._operational_summary(indicator, potential, score, rh),
            "strengths": (strengths[:3] + score_strengths)[:5] or ["Nao houve dados suficientes para identificar pontos fortes com seguranca."],
            "attention_points": (attention[:3] + score_attention)[:5] or ["Nao houve dados suficientes para identificar pontos de atencao com seguranca."],
            "recurring_themes": (general[:3] + themes)[:5] or ["Dados qualitativos insuficientes para temas recorrentes."],
            "qualitative_alerts": [],
            "suggested_feedback": (
                self._score_based_feedback(general_average, competency_averages) + " "
                + self._operational_feedback(indicator, potential, score, rh) + " "
                "Para os proximos 6 meses, recomenda-se combinar metas objetivas de entrega, acompanhamento mensal dos pontos de atencao e registro de evidencias em projetos. "
                "Esta sugestao nao altera nota, categoria ou decisao final."
            ),
            "manager_review_required": True,
        }

    @staticmethod
    def _safe_error_message(exc: Exception) -> str:
        message = str(exc)
        if "key=" in message:
            message = message.split("key=", 1)[0] + "key=***"
        return message[:500]

    def _reviews_for_employee(self, employee_id: int) -> list[Review360]:
        return self._filter_self_reviews(
            self.db.query(Review360).filter(Review360.evaluated_id == employee_id).all(),
            employee_id,
        )

    def _reviews(self, cycle_id: int, employee_id: int) -> list[Review360]:
        return self._filter_self_reviews(self._raw_reviews(cycle_id, employee_id), employee_id)

    def _raw_reviews(self, cycle_id: int, employee_id: int) -> list[Review360]:
        return self.db.query(Review360).filter(Review360.cycle_id == cycle_id, Review360.evaluated_id == employee_id).all()

    def _indicator(self, cycle_id: int, employee_id: int) -> PerformanceIndicator | None:
        query = self.db.query(PerformanceIndicator).filter(
            PerformanceIndicator.cycle_id == cycle_id,
            PerformanceIndicator.employee_id == employee_id,
        )
        return query.first() if hasattr(query, "first") else None

    def _potential(self, cycle_id: int, employee_id: int) -> PotentialScore | None:
        query = self.db.query(PotentialScore).filter(
            PotentialScore.cycle_id == cycle_id,
            PotentialScore.employee_id == employee_id,
        )
        return query.first() if hasattr(query, "first") else None

    def _score(self, cycle_id: int, employee_id: int) -> EvaluationScore | None:
        query = self.db.query(EvaluationScore).filter(
            EvaluationScore.cycle_id == cycle_id,
            EvaluationScore.employee_id == employee_id,
        )
        return query.first() if hasattr(query, "first") else None

    def _rh_data(self, cycle_id: int, employee_id: int) -> EmployeeRhData | None:
        query = self.db.query(EmployeeRhData).filter(
            EmployeeRhData.cycle_id == cycle_id,
            EmployeeRhData.employee_id == employee_id,
        )
        return query.first() if hasattr(query, "first") else None

    @classmethod
    def _filter_self_reviews(cls, reviews: list[Review360], employee_id: int) -> list[Review360]:
        return [
            row for row in reviews
            if not cls._is_self_review(row, employee_id)
        ]

    @staticmethod
    def _is_self_review(row: Review360, employee_id: int) -> bool:
        if row.evaluator_id and row.evaluator_id == employee_id:
            return True
        if row.evaluator_name and row.evaluated_name:
            return row.evaluator_name.strip().casefold() == row.evaluated_name.strip().casefold()
        return row.relation_type == "SELF"

    @staticmethod
    def _collect_terms(values: list[str | None]) -> list[str]:
        terms: list[str] = []
        for value in values:
            text = (value or "").strip()
            if text and text not in terms:
                terms.append(text[:180])
        return terms

    @staticmethod
    def _competency_averages(reviews: list[Review360]) -> dict[str, float]:
        fields = ["communication_score", "teamwork_score", "commitment_score", "autonomy_score", "quality_score", "problem_solving_score"]
        averages: dict[str, float] = {}
        for field in fields:
            values = [getattr(row, field) for row in reviews if getattr(row, field) is not None]
            if values:
                averages[field] = round(sum(values) / len(values), 2)
        return averages

    @classmethod
    def _rank_competencies(cls, competency_averages: dict[str, float], reverse: bool) -> list[dict[str, float | str]]:
        ordered = sorted(competency_averages.items(), key=lambda item: item[1], reverse=reverse)
        return [
            {"competency": cls._competency_label(field), "average": score}
            for field, score in ordered[:3]
        ]

    @staticmethod
    def _review_payload(row: Review360) -> dict[str, Any]:
        return {
            "relation_type": row.relation_type,
            "general_score": row.general_score or row.score,
            "communication_score": row.communication_score,
            "teamwork_score": row.teamwork_score,
            "commitment_score": row.commitment_score,
            "autonomy_score": row.autonomy_score,
            "quality_score": row.quality_score,
            "problem_solving_score": row.problem_solving_score,
            "strengths_comment": row.strengths_comment,
            "improvement_comment": row.improvement_comment,
            "general_comment": row.general_comment or row.comment,
        }

    @staticmethod
    def _relation_averages(reviews: list[Review360]) -> dict[str, float]:
        averages: dict[str, float] = {}
        for relation in BEHAVIOR_WEIGHTS:
            values = [row.general_score or row.score for row in reviews if row.relation_type == relation and (row.general_score is not None or row.score is not None)]
            if values:
                averages[relation] = round(sum(values) / len(values), 2)
        return averages

    @staticmethod
    def _competency_label(field: str) -> str:
        labels = {
            "communication_score": "comunicacao",
            "teamwork_score": "trabalho em equipe",
            "commitment_score": "comprometimento",
            "autonomy_score": "autonomia",
            "quality_score": "qualidade do trabalho",
            "problem_solving_score": "orientacao para resultados",
        }
        return labels.get(field, field)

    @classmethod
    def _score_based_strengths(cls, competency_averages: dict[str, float]) -> list[str]:
        ordered = sorted(competency_averages.items(), key=lambda item: item[1], reverse=True)
        return [
            f"{cls._competency_label(field).capitalize()} aparece como ponto forte nas avaliacoes, com media {score:.1f}."
            for field, score in ordered
            if score >= 75
        ][:3]

    @classmethod
    def _score_based_attention_points(cls, competency_averages: dict[str, float]) -> list[str]:
        ordered = sorted(competency_averages.items(), key=lambda item: item[1])
        attention = [
            f"{cls._competency_label(field).capitalize()} merece acompanhamento, com media {score:.1f}."
            for field, score in ordered
            if score < 70
        ]
        if attention:
            return attention[:3]
        if ordered:
            field, score = ordered[0]
            return [f"Menor media relativa em {cls._competency_label(field)} ({score:.1f}); validar contexto na calibracao."]
        return []

    @staticmethod
    def _score_based_themes(general_average: float | None, relation_averages: dict[str, float]) -> list[str]:
        themes: list[str] = []
        if general_average is not None:
            themes.append(f"Media geral das avaliacoes 360: {general_average:.1f}.")
        for relation, score in relation_averages.items():
            themes.append(f"Media por perfil {relation}: {score:.1f}.")
        return themes[:5]

    @staticmethod
    def _operational_themes(
        indicator: PerformanceIndicator | None,
        potential: PotentialScore | None,
        score: EvaluationScore | None,
        rh: EmployeeRhData | None,
    ) -> list[str]:
        themes: list[str] = []
        if indicator and indicator.rpm_normalized is not None:
            themes.append(f"RPM recalculado disponivel: {indicator.rpm_normalized:.1f}%.")
        if indicator and indicator.ihpe_normalized is not None:
            themes.append(f"IHPE recalculado disponivel: {indicator.ihpe_normalized:.1f}%.")
        if potential:
            themes.append(f"Nota do gestor: {potential.score:.1f}.")
        if score and score.preliminary_final_score is not None:
            themes.append(f"Score final preliminar calculado: {score.preliminary_final_score:.1f}.")
        if rh:
            themes.append(f"Elegibilidade RH: {rh.eligibility_reason or 'nao informada'}.")
        return themes

    @staticmethod
    def _operational_summary(
        indicator: PerformanceIndicator | None,
        potential: PotentialScore | None,
        score: EvaluationScore | None,
        rh: EmployeeRhData | None,
    ) -> str:
        parts: list[str] = []
        if indicator and (indicator.rpm_normalized is not None or indicator.ihpe_normalized is not None):
            parts.append(
                " Indicadores objetivos disponiveis: "
                f"RPM {indicator.rpm_normalized:.1f}%" if indicator.rpm_normalized is not None else " Indicador RPM nao informado"
            )
            if indicator.ihpe_normalized is not None:
                parts.append(f"e IHPE {indicator.ihpe_normalized:.1f}%.")
        if potential:
            parts.append(f" Nota do gestor: {potential.score:.1f}.")
        if score and score.preliminary_final_score is not None:
            parts.append(f" Score final preliminar: {score.preliminary_final_score:.1f}.")
        if rh:
            level = f"ANC {rh.career_level}" if rh.career_level is not None else "nivel nao informado"
            parts.append(f" Contexto RH: {level}; {rh.eligibility_reason or 'elegibilidade nao informada'}.")
        return " ".join(parts)

    @staticmethod
    def _operational_feedback(
        indicator: PerformanceIndicator | None,
        potential: PotentialScore | None,
        score: EvaluationScore | None,
        rh: EmployeeRhData | None,
    ) -> str:
        parts: list[str] = []
        if indicator and indicator.rpm_normalized is not None and indicator.ihpe_normalized is not None:
            parts.append(
                f"Na dimensao objetiva, RPM de {indicator.rpm_normalized:.1f}% e IHPE de {indicator.ihpe_normalized:.1f}% devem ser discutidos junto das entregas de valor."
            )
        elif indicator and indicator.rpm_normalized is not None:
            parts.append(f"Na dimensao objetiva, RPM de {indicator.rpm_normalized:.1f}% deve ser considerado junto das entregas.")
        elif indicator and indicator.ihpe_normalized is not None:
            parts.append(f"Na dimensao objetiva, IHPE de {indicator.ihpe_normalized:.1f}% deve ser considerado junto das entregas.")
        if potential:
            parts.append(f"A nota do gestor ({potential.score:.1f}) deve orientar desafios e acompanhamento do ciclo seguinte.")
        if rh and not rh.eligible_for_merit:
            parts.append(f"Mesmo com desempenho positivo, ha restricao de elegibilidade: {rh.eligibility_reason}.")
        if rh and rh.is_level_one_separate_budget:
            parts.append("Por ser nivel 1, a avaliacao deve ser lida na regra de verba separada e requisito minimo de desempenho muito bom.")
        if score and score.preliminary_final_score is not None:
            parts.append(f"O score preliminar atual e {score.preliminary_final_score:.1f}, sujeito a calibracao gerencial.")
        return " ".join(parts)

    @classmethod
    def _score_based_summary(
        cls,
        employee: Employee,
        review_count: int,
        general_average: float | None,
        competency_averages: dict[str, float],
    ) -> str:
        if general_average is None:
            return f"Analise local de {employee.name}: nao ha notas suficientes para consolidar tendencia qualitativa."
        strengths = cls._score_based_strengths(competency_averages)
        attention = cls._score_based_attention_points(competency_averages)
        summary = f"Analise local de {employee.name} baseada em {review_count} avaliacao(oes) 360, com media geral {general_average:.1f}."
        if strengths:
            summary += f" Destaque principal: {strengths[0]}"
        if attention:
            summary += f" Ponto para calibracao: {attention[0]}"
        if competency_averages:
            ordered = sorted(competency_averages.items(), key=lambda item: item[1], reverse=True)
            top_field, top_score = ordered[0]
            low_field, low_score = ordered[-1]
            summary += (
                f" A leitura numerica sugere maior reconhecimento em {cls._competency_label(top_field)} ({top_score:.1f}) "
                f"e menor avaliacao relativa em {cls._competency_label(low_field)} ({low_score:.1f})."
            )
        return summary

    @classmethod
    def _score_based_feedback(cls, general_average: float | None, competency_averages: dict[str, float]) -> str:
        strengths = cls._score_based_strengths(competency_averages)
        attention = cls._score_based_attention_points(competency_averages)
        parts = []
        if general_average is not None:
            parts.append(f"Reconhecer a media geral de avaliacao 360 ({general_average:.1f}) e discutir exemplos concretos que sustentem essa percepcao.")
        if strengths:
            parts.append(f"Reforcar o ponto forte identificado: {strengths[0]}")
        if attention:
            parts.append(f"Combinar acao objetiva para o ponto de atencao: {attention[0]}")
        if competency_averages:
            low_items = sorted(competency_averages.items(), key=lambda item: item[1])[:2]
            development = ", ".join(f"{cls._competency_label(field)} ({score:.1f})" for field, score in low_items)
            parts.append(f"Na conversa de feedback, validar se {development} refletem contexto do periodo ou oportunidades reais de desenvolvimento.")
        return " ".join(parts) if parts else "Validar a avaliacao qualitativa com exemplos concretos na reuniao de calibracao."

