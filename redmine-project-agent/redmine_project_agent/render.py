from __future__ import annotations

import json

from .advisor import AdvisoryReport


def render_json(report: AdvisoryReport) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)


def render_markdown(report: AdvisoryReport) -> str:
    lines = [
        f"# Avaliação consultiva: {report.project_name}",
        "",
        f"**Status:** {report.status.upper()}",
        f"**Score:** {report.score}/100",
        f"**Confiança:** {report.confidence:.2f}",
        "",
        "## Resumo",
        report.summary,
        "",
        "## Principais riscos",
    ]
    if report.risks:
        for risk in report.risks:
            lines.extend([
                f"### {risk.title} ({risk.severity})",
                *[f"- {item}" for item in risk.evidence],
                "",
            ])
    else:
        lines.append("- Nenhum risco relevante pelos critérios atuais.")
        lines.append("")

    lines.extend(["## Sugestões", *[f"- {item}" for item in report.suggestions], ""])
    lines.extend(["## Perguntas para o gestor", *[f"- {item}" for item in report.manager_questions], ""])
    lines.extend(["## Métricas", "```json", json.dumps(report.metrics, ensure_ascii=False, indent=2), "```"])
    return "\n".join(lines)
