from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.adapters.redmine import RedmineAdapter
from app.assistant.actions.base import ActionResult
from app.assistant.schemas import AssistantPlan
from app.models import Connector, User


@dataclass(frozen=True)
class AdvisorMetrics:
    total_issues: int
    open_issues: int
    overdue: list[dict[str, Any]]
    stale: list[dict[str, Any]]
    unassigned: list[dict[str, Any]]
    high_priority: list[dict[str, Any]]
    in_progress: list[dict[str, Any]]


class ProjectAdvisorAction:
    domain = "project_advisor"

    def preview(self, db: Session, plan: AssistantPlan, user: User | None) -> dict[str, Any]:
        params = plan.extracted_params or {}
        return {
            "title": "Avaliacao consultiva de projeto",
            "domain": self.domain,
            "action": "analyze",
            "params": {
                "project_id": params.get("project_id"),
                "days_stale": params.get("days_stale") or 7,
            },
            "missing_params": plan.missing_params,
            "impact": "Somente consulta dados do Redmine. Nao cria, edita, comenta ou altera demandas.",
            "read_only": True,
        }

    def execute(self, db: Session, plan: AssistantPlan, user: User | None) -> ActionResult:
        params = plan.extracted_params or {}
        connector = self._redmine_connector(db)
        if not connector:
            return ActionResult(
                message="Nao encontrei um conector Redmine ativo para avaliar o projeto.",
                data={"status": "missing_connector"},
                success=False,
                errors=["missing_redmine_connector"],
            )

        requested_project_id = str(params.get("project_id") or "").strip()
        project_ids = self._scoped_project_ids(connector, requested_project_id)
        if not project_ids:
            return ActionResult(
                message="Informe qual projeto do Redmine devo avaliar ou configure project_ids no conector Redmine.",
                data={"status": "missing_project_id"},
                success=False,
                errors=["missing_project_id"],
            )

        days_stale = int(params.get("days_stale") or 7)
        config = connector.config_json or {}
        adapter = RedmineAdapter(base_url=config.get("base_url"), api_key=config.get("api_key"))

        try:
            raw_issues: list[dict[str, Any]] = []
            for project_id in project_ids:
                raw_issues.extend(
                    adapter.fetch_issues(
                        project_id=project_id,
                        start_date=date.today() - timedelta(days=3650),
                        end_date=date.today(),
                        status_id="*",
                        apply_date_filter=False,
                    )
                )
            issues = self._dedupe_issues(
                issue
                for issue in raw_issues
                if any(self._issue_matches_project_scope(issue, project_id) for project_id in project_ids)
            )
        except Exception as exc:  # noqa: BLE001
            return ActionResult(
                message=f"Nao consegui consultar o Redmine para avaliar o projeto {', '.join(project_ids)}: {exc}",
                data={"status": "redmine_error", "project_ids": project_ids},
                success=False,
                errors=["redmine_query_failed"],
            )

        metrics = self._metrics(issues, days_stale=days_stale)
        score = self._score(metrics)
        status = self._status(score)
        risks = self._risks(metrics, days_stale=days_stale)
        suggestions = self._suggestions(metrics, status)
        questions = self._questions(metrics)
        message = self._message(", ".join(project_ids), status, score, metrics, risks, suggestions)

        return ActionResult(
            message=message,
            data={
                "agent": "project_advisor",
                "read_only": True,
                "project_ids": project_ids,
                "status": status,
                "score": score,
                "metrics": {
                    "raw_issues_from_redmine": len(raw_issues),
                    "total_issues": metrics.total_issues,
                    "open_issues": metrics.open_issues,
                    "overdue_count": len(metrics.overdue),
                    "stale_count": len(metrics.stale),
                    "unassigned_count": len(metrics.unassigned),
                    "high_priority_count": len(metrics.high_priority),
                    "in_progress_count": len(metrics.in_progress),
                },
                "risks": risks,
                "suggestions": suggestions,
                "manager_questions": questions,
                "source": {
                    "type": "redmine",
                    "connector_id": connector.id,
                    "connector_project_ids": self._connector_project_ids(connector),
                    "scope_enforced": True,
                },
            },
        )

    def _redmine_connector(self, db: Session) -> Connector | None:
        return (
            db.query(Connector)
            .filter(Connector.type == "redmine", Connector.is_active.is_(True))
            .order_by(Connector.id.asc())
            .first()
        )

    def _default_project_id(self, connector: Connector) -> str | None:
        project_ids = self._connector_project_ids(connector)
        if len(project_ids) == 1:
            return project_ids[0]
        return None

    def _connector_project_ids(self, connector: Connector) -> list[str]:
        project_ids = (connector.config_json or {}).get("project_ids") or []
        if not isinstance(project_ids, list):
            return []
        return [str(item).strip() for item in project_ids if str(item).strip()]

    def _scoped_project_ids(self, connector: Connector, requested_project_id: str | None) -> list[str]:
        configured = self._connector_project_ids(connector)
        requested = str(requested_project_id or "").strip()
        if not configured:
            return [requested] if requested else []
        if not requested:
            return configured
        for configured_project in configured:
            if self._project_scope_matches(configured_project, requested):
                return [configured_project]
        return configured

    def _dedupe_issues(self, issues: Any) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for issue in issues:
            key = str(issue.get("id") or "")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            result.append(issue)
        return result

    def _issue_matches_project_scope(self, issue: dict[str, Any], project_id: str | None) -> bool:
        if not project_id:
            return True
        project = issue.get("project")
        if not isinstance(project, dict):
            return self._project_scope_matches(project_id, project)

        candidates = [
            project.get("id"),
            project.get("identifier"),
            project.get("name"),
        ]
        return any(self._project_scope_matches(project_id, item) for item in candidates if item not in (None, ""))

    def _project_scope_matches(self, expected: Any, candidate: Any) -> bool:
        expected_compact = self._normalize_project_scope_value(expected)
        candidate_compact = self._normalize_project_scope_value(candidate)
        if not expected_compact or not candidate_compact:
            return False
        if expected_compact == candidate_compact:
            return True

        expected_tokens = self._project_scope_tokens(expected)
        candidate_tokens = self._project_scope_tokens(candidate)
        if len(expected_tokens) != len(candidate_tokens):
            return False
        return all(
            left == right
            or (len(left) >= 3 and right.startswith(left))
            or (len(right) >= 3 and left.startswith(right))
            for left, right in zip(expected_tokens, candidate_tokens)
        )

    def _normalize_project_scope_value(self, value: Any) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return re.sub(r"[^a-zA-Z0-9]+", "", normalized).casefold()

    def _project_scope_tokens(self, value: Any) -> list[str]:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return [token.casefold() for token in re.split(r"[^a-zA-Z0-9]+", normalized) if token]
    def _metrics(self, issues: list[dict[str, Any]], days_stale: int) -> AdvisorMetrics:
        today = date.today()
        stale_limit = datetime.now().astimezone() - timedelta(days=days_stale)
        open_issues = [issue for issue in issues if not self._is_closed(issue)]
        overdue = [issue for issue in open_issues if self._due_date(issue) and self._due_date(issue) < today]
        stale = [issue for issue in open_issues if self._updated_on(issue) and self._updated_on(issue) < stale_limit]
        unassigned = [issue for issue in open_issues if not issue.get("assigned_to")]
        high_priority = [issue for issue in open_issues if self._is_high_priority(issue)]
        in_progress = [issue for issue in open_issues if self._status_name(issue).lower() in {"em andamento", "in progress", "execucao", "execucao", "desenvolvimento"}]
        return AdvisorMetrics(
            total_issues=len(issues),
            open_issues=len(open_issues),
            overdue=overdue,
            stale=stale,
            unassigned=unassigned,
            high_priority=high_priority,
            in_progress=in_progress,
        )

    def _score(self, metrics: AdvisorMetrics) -> int:
        score = 0
        score += min(30, 10 + 4 * len(metrics.high_priority)) if metrics.high_priority else 0
        score += min(28, 8 + 3 * len(metrics.overdue)) if metrics.overdue else 0
        score += min(20, 5 + 2 * len(metrics.stale)) if metrics.stale else 0
        score += min(14, 4 + 2 * len(metrics.unassigned)) if metrics.unassigned else 0
        if metrics.open_issues > 25:
            score += 8
        return min(score, 100)

    def _status(self, score: int) -> str:
        if score >= 70:
            return "vermelho"
        if score >= 45:
            return "laranja"
        if score >= 20:
            return "amarelo"
        return "verde"

    def _risks(self, metrics: AdvisorMetrics, days_stale: int) -> list[dict[str, Any]]:
        risks: list[dict[str, Any]] = []
        if metrics.high_priority:
            risks.append(self._risk("Demandas abertas de alta prioridade", "alto", metrics.high_priority))
        if metrics.overdue:
            severity = "alto" if len(metrics.overdue) >= 3 else "medio"
            risks.append(self._risk("Demandas atrasadas", severity, metrics.overdue))
        if metrics.stale:
            risks.append(self._risk(f"Demandas sem atualizacao ha {days_stale}+ dias", "medio", metrics.stale))
        if metrics.unassigned:
            risks.append(self._risk("Demandas sem responsavel", "medio", metrics.unassigned))
        return risks

    def _suggestions(self, metrics: AdvisorMetrics, status: str) -> list[str]:
        suggestions: list[str] = []
        if metrics.high_priority:
            suggestions.append("Revisar as demandas de alta prioridade e confirmar prazo, responsavel e proximo passo.")
        if metrics.overdue:
            suggestions.append("Separar as demandas atrasadas entre bloqueio real, replanejamento e baixa prioridade.")
        if metrics.stale:
            suggestions.append("Pedir atualizacao objetiva das demandas sem movimentacao recente.")
        if metrics.unassigned:
            suggestions.append("Atribuir responsaveis antes de discutir prazo ou cobranca.")
        if status in {"laranja", "vermelho"}:
            suggestions.append("Fazer uma conversa curta de gestao sobre riscos, bloqueios e decisoes da semana.")
        return suggestions or ["Manter acompanhamento normal e revisar novamente no proximo ciclo."]

    def _questions(self, metrics: AdvisorMetrics) -> list[str]:
        questions: list[str] = []
        if metrics.overdue:
            questions.append("As demandas atrasadas ainda fazem parte do escopo atual?")
        if metrics.high_priority:
            questions.append("As prioridades altas tem plano claro de conclusao?")
        if metrics.stale:
            questions.append("A falta de atualizacao indica bloqueio ou apenas falta de registro?")
        if metrics.unassigned:
            questions.append("Quem deve assumir as demandas sem responsavel?")
        return questions or ["Existe algum risco relevante fora do Redmine que precisa entrar no acompanhamento?"]

    def _message(
        self,
        project_id: str,
        status: str,
        score: int,
        metrics: AdvisorMetrics,
        risks: list[dict[str, Any]],
        suggestions: list[str],
    ) -> str:
        lines = [
            f"Analise consultiva do projeto {project_id}: status {status.upper()} ({score}/100).",
            f"Analisei {metrics.total_issues} demandas; {metrics.open_issues} estao abertas.",
            "",
            "Principais sinais:",
        ]
        if risks:
            for risk in risks[:4]:
                lines.append(f"- {risk['title']} ({risk['severity']}): {len(risk['items'])} evidencia(s).")
        else:
            lines.append("- Nao encontrei sinais fortes de risco pelos criterios atuais.")
        lines.extend(["", "Sugestoes:"])
        lines.extend(f"- {item}" for item in suggestions[:5])
        lines.append("\nEsta avaliacao e somente leitura; nada foi alterado no Redmine.")
        return "\n".join(lines)

    def _risk(self, title: str, severity: str, issues: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "title": title,
            "severity": severity,
            "items": [self._issue_item(issue) for issue in issues[:5]],
        }

    def _issue_item(self, issue: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": issue.get("id"),
            "subject": issue.get("subject"),
            "status": self._status_name(issue),
            "priority": self._priority_name(issue),
            "assigned_to": self._name(issue.get("assigned_to")) or "sem responsavel",
            "due_date": issue.get("due_date"),
            "updated_on": issue.get("updated_on"),
        }

    def _is_closed(self, issue: dict[str, Any]) -> bool:
        status = issue.get("status") or {}
        if isinstance(status, dict) and status.get("is_closed") is True:
            return True
        return self._status_name(issue).lower() in {"fechado", "closed", "resolvido", "concluido", "concluído"}

    def _is_high_priority(self, issue: dict[str, Any]) -> bool:
        priority = self._priority_name(issue).lower()
        return any(token in priority for token in ("alta", "high", "urgente", "imediata", "immediate"))

    def _name(self, value: Any) -> str | None:
        if isinstance(value, dict):
            return str(value.get("name") or "").strip() or None
        if value:
            return str(value).strip()
        return None

    def _status_name(self, issue: dict[str, Any]) -> str:
        return self._name(issue.get("status")) or ""

    def _priority_name(self, issue: dict[str, Any]) -> str:
        return self._name(issue.get("priority")) or ""

    def _due_date(self, issue: dict[str, Any]) -> date | None:
        value = issue.get("due_date")
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    def _updated_on(self, issue: dict[str, Any]) -> datetime | None:
        value = issue.get("updated_on")
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.astimezone()
        return parsed

