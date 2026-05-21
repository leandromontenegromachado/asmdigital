from __future__ import annotations

from sqlalchemy.orm import Session

from app.assistant.actions.base import ActionResult, compact_items
from app.assistant.actions.list_late_projects import format_late_projects_message, list_late_projects
from app.assistant.schemas import AssistantPlan
from app.models import PromptReportTemplate, Report, User
from app.services.prompt_report_service import run_prompt_report_template


class ReportsAction:
    domain = "reports"

    def preview(self, db: Session, plan: AssistantPlan, user: User | None) -> dict:
        return {
            "title": "Relatorio",
            "domain": plan.domain,
            "action": plan.action,
            "params": plan.extracted_params,
            "missing_params": plan.missing_params,
            "impact": "Executar relatorio pode criar uma nova execucao e consultar conectores externos.",
        }

    def execute(self, db: Session, plan: AssistantPlan, user: User | None) -> ActionResult:
        if plan.action == "list_late_projects":
            data = list_late_projects()
            return ActionResult(message=format_late_projects_message(data), data=data)

        if plan.action == "list":
            reports = db.query(Report).order_by(Report.generated_at.desc()).limit(20).all()
            items = [
                {"id": item.id, "type": item.type, "status": item.status, "generated_at": item.generated_at.isoformat() if item.generated_at else None}
                for item in reports
            ]
            return ActionResult(message=f"Encontrei {len(items)} relatorios recentes.", data=compact_items(items))

        if plan.action == "run_report":
            params = plan.extracted_params or {}
            template_id = params.get("template_id")
            if template_id:
                template = db.query(PromptReportTemplate).filter(PromptReportTemplate.id == int(template_id)).first()
                if not template:
                    return ActionResult(message="Template de relatorio nao encontrado.", data={}, success=False, errors=["template_not_found"])
                report, filters = run_prompt_report_template(db, template, trigger="assistant")
                return ActionResult(
                    message=f"Relatorio #{report.id} executado.",
                    data={"report_id": report.id, "status": report.status, "filters": filters},
                )
            return ActionResult(
                message="Preparei a execucao, mas preciso do template ou conector para rodar o relatorio real.",
                data={"status": "needs_input", "params": params},
                success=False,
                errors=["missing_template_id"],
            )

        return ActionResult(message="Acao de relatorio nao suportada.", data={}, success=False, errors=["unsupported_action"])
