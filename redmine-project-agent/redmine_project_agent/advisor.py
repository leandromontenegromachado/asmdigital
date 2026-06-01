from __future__ import annotations

from dataclasses import asdict, dataclass

from .metrics import ProjectMetrics, calculate_metrics
from .models import Issue, ProjectSnapshot


@dataclass(frozen=True)
class RiskItem:
    title: str
    severity: str
    evidence: list[str]


@dataclass(frozen=True)
class AdvisoryReport:
    project_id: int | str
    project_name: str
    status: str
    score: int
    summary: str
    risks: list[RiskItem]
    suggestions: list[str]
    manager_questions: list[str]
    metrics: dict
    confidence: float

    def to_dict(self) -> dict:
        return asdict(self)


def issue_ref(issue: Issue) -> str:
    owner = issue.assigned_to or "sem responsável"
    return f"#{issue.id} - {issue.subject} ({issue.status}, {owner})"


def evaluate_project(snapshot: ProjectSnapshot, days_stale: int = 7) -> AdvisoryReport:
    metrics = calculate_metrics(snapshot, days_stale=days_stale)
    risks: list[RiskItem] = []
    score = 0

    if metrics.high_priority_open_issues:
        score += min(30, 10 + 4 * len(metrics.high_priority_open_issues))
        risks.append(RiskItem(
            title="Issues abertas de alta prioridade",
            severity="alto",
            evidence=[issue_ref(issue) for issue in metrics.high_priority_open_issues[:5]],
        ))

    if metrics.overdue_issues:
        score += min(28, 8 + 3 * len(metrics.overdue_issues))
        risks.append(RiskItem(
            title="Issues atrasadas",
            severity="alto" if len(metrics.overdue_issues) >= 3 else "médio",
            evidence=[issue_ref(issue) for issue in metrics.overdue_issues[:5]],
        ))

    if metrics.stale_issues:
        score += min(20, 5 + 2 * len(metrics.stale_issues))
        risks.append(RiskItem(
            title=f"Issues sem atualização há {days_stale}+ dias",
            severity="médio",
            evidence=[issue_ref(issue) for issue in metrics.stale_issues[:5]],
        ))

    if metrics.unassigned_issues:
        score += min(14, 4 + 2 * len(metrics.unassigned_issues))
        risks.append(RiskItem(
            title="Issues sem responsável",
            severity="médio",
            evidence=[issue_ref(issue) for issue in metrics.unassigned_issues[:5]],
        ))

    if metrics.due_soon_versions and metrics.open_issues > 0:
        score += 8
        risks.append(RiskItem(
            title="Versões próximas com pendências abertas",
            severity="médio",
            evidence=[f"Versão próxima: {name}" for name in metrics.due_soon_versions[:5]],
        ))

    score = min(score, 100)
    status = classify_status(score)
    suggestions = build_suggestions(metrics, status)
    questions = build_questions(metrics)
    summary = build_summary(snapshot.project_name, status, metrics)
    confidence = confidence_for(metrics)

    return AdvisoryReport(
        project_id=snapshot.project_id,
        project_name=snapshot.project_name,
        status=status,
        score=score,
        summary=summary,
        risks=risks,
        suggestions=suggestions,
        manager_questions=questions,
        metrics={
            "total_issues": metrics.total_issues,
            "open_issues": metrics.open_issues,
            "closed_issues": metrics.closed_issues,
            "completion_rate": round(metrics.completion_rate, 2),
            "overdue_count": len(metrics.overdue_issues),
            "unassigned_count": len(metrics.unassigned_issues),
            "stale_count": len(metrics.stale_issues),
            "high_priority_open_count": len(metrics.high_priority_open_issues),
            "in_progress_count": metrics.in_progress_count,
            "due_soon_versions": metrics.due_soon_versions,
            "by_assignee": metrics.by_assignee,
        },
        confidence=confidence,
    )


def classify_status(score: int) -> str:
    if score >= 70:
        return "vermelho"
    if score >= 45:
        return "laranja"
    if score >= 20:
        return "amarelo"
    return "verde"


def build_summary(project_name: str, status: str, metrics: ProjectMetrics) -> str:
    if status == "verde":
        return f"{project_name} parece saudável pelos dados analisados, sem sinais fortes de risco operacional."
    if status == "amarelo":
        return f"{project_name} exige atenção: há sinais de risco, mas ainda parecem tratáveis com acompanhamento."
    if status == "laranja":
        return f"{project_name} tem risco relevante e deve entrar no radar de gestão nos próximos dias."
    return f"{project_name} está em risco alto pelos dados analisados e exige ação de gestão."


def build_suggestions(metrics: ProjectMetrics, status: str) -> list[str]:
    suggestions: list[str] = []
    if metrics.high_priority_open_issues:
        suggestions.append("Revisar as issues de alta prioridade e confirmar se todas têm plano claro de conclusão.")
    if metrics.overdue_issues:
        suggestions.append("Avaliar replanejamento ou desbloqueio das issues atrasadas.")
    if metrics.stale_issues:
        suggestions.append("Pedir atualização objetiva das issues sem movimentação recente.")
    if metrics.unassigned_issues:
        suggestions.append("Atribuir responsáveis para issues sem dono antes de discutir prazo.")
    if metrics.due_soon_versions:
        suggestions.append("Revisar a viabilidade das versões próximas com pendências abertas.")
    if not suggestions:
        suggestions.append("Manter acompanhamento normal e revisar novamente no próximo ciclo.")
    if status in {"laranja", "vermelho"}:
        suggestions.append("Priorizar uma conversa de gestão curta sobre riscos, bloqueios e próximos passos.")
    return suggestions


def build_questions(metrics: ProjectMetrics) -> list[str]:
    questions: list[str] = []
    if metrics.overdue_issues:
        questions.append("As issues atrasadas ainda pertencem ao escopo atual ou precisam ser replanejadas?")
    if metrics.high_priority_open_issues:
        questions.append("As issues de alta prioridade têm responsável, prazo e próximo passo claros?")
    if metrics.stale_issues:
        questions.append("A falta de atualização indica bloqueio real ou apenas ausência de registro?")
    if metrics.unassigned_issues:
        questions.append("Quem deve assumir as issues sem responsável?")
    if not questions:
        questions.append("Há algum risco não registrado no Redmine que deveria aparecer no acompanhamento?")
    return questions


def confidence_for(metrics: ProjectMetrics) -> float:
    if metrics.total_issues == 0:
        return 0.35
    if metrics.open_issues < 3:
        return 0.55
    return 0.78
