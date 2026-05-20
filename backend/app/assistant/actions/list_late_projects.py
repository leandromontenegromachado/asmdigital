from __future__ import annotations

from datetime import date
from typing import Any


def list_late_projects() -> dict[str, Any]:
    today = date.today()
    rows = [
        {
            "project": "Portal de Servicos",
            "responsible": "Maria Silva",
            "due_date": "2026-05-10",
            "days_late": max(0, (today - date(2026, 5, 10)).days),
            "status": "Atrasado",
        },
        {
            "project": "Integracao Redmine",
            "responsible": "Leandro Montenegro Machado",
            "due_date": "2026-05-14",
            "days_late": max(0, (today - date(2026, 5, 14)).days),
            "status": "Atrasado",
        },
        {
            "project": "Painel Executivo",
            "responsible": "Alessandra Martins Nunes",
            "due_date": "2026-05-18",
            "days_late": max(0, (today - date(2026, 5, 18)).days),
            "status": "Atrasado",
        },
    ]
    return {"total": len(rows), "items": rows, "source": "mock"}


def format_late_projects_message(data: dict[str, Any]) -> str:
    rows = data.get("items") or []
    if not rows:
        return "Nao encontrei projetos em atraso."
    lines = [f"Encontrei {len(rows)} projetos em atraso:"]
    for item in rows[:10]:
        lines.append(
            f"- {item['project']}: {item['days_late']} dias em atraso, responsavel {item['responsible']}."
        )
    if data.get("source") == "mock":
        lines.append("Dados mockados nesta primeira versao do Assistant Core.")
    return "\n".join(lines)
