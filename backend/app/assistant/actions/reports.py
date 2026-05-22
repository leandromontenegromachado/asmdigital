from __future__ import annotations

from sqlalchemy.orm import Session

from app.assistant.actions.base import ActionResult, compact_items
from app.assistant.actions.list_late_projects import format_late_projects_message, list_late_projects
from app.assistant.schemas import AssistantPlan
from app.models import PromptReportTemplate, Report, ReportRow, User
from app.services.prompt_report_service import PromptInterpretationError, run_prompt_report_template


class ReportsAction:
    domain = "reports"

    def preview(self, db: Session, plan: AssistantPlan, user: User | None) -> dict:
        params = plan.extracted_params or {}
        action = self._canonical_action(plan.action)
        selected_template = None
        template_id = params.get("template_id")
        if template_id:
            selected_template = db.query(PromptReportTemplate).filter(PromptReportTemplate.id == int(template_id)).first()
        elif action == "run_report":
            selected_template = self._default_template(db)
        return {
            "title": "Relatorio",
            "domain": plan.domain,
            "action": action,
            "params": {
                **params,
                "template_id": selected_template.id if selected_template else template_id,
                "template_name": selected_template.name if selected_template else None,
                "prompt": self._prompt_from_params(plan, params) if action == "run_report" else None,
            },
            "missing_params": plan.missing_params,
            "impact": "Executar relatorio pode criar uma nova execucao e consultar conectores externos.",
        }

    def execute(self, db: Session, plan: AssistantPlan, user: User | None) -> ActionResult:
        action = self._canonical_action(plan.action)
        if action == "list_late_projects":
            data = list_late_projects()
            return ActionResult(message=format_late_projects_message(data), data=data)

        if action == "list":
            reports = db.query(Report).order_by(Report.generated_at.desc()).limit(20).all()
            items = [
                {"id": item.id, "type": item.type, "status": item.status, "generated_at": item.generated_at.isoformat() if item.generated_at else None}
                for item in reports
            ]
            return ActionResult(message=f"Encontrei {len(items)} relatorios recentes.", data=compact_items(items))

        if action == "run_report":
            params = plan.extracted_params or {}
            template_id = params.get("template_id")
            template = None
            if template_id:
                template = db.query(PromptReportTemplate).filter(PromptReportTemplate.id == int(template_id)).first()
                if not template:
                    return ActionResult(message="Template de relatorio nao encontrado.", data={}, success=False, errors=["template_not_found"])
            else:
                template = self._default_template(db)
            if not template:
                return ActionResult(
                    message="Nao encontrei template de relatorio ativo para executar.",
                    data={"status": "needs_input", "params": params},
                    success=False,
                    errors=["missing_template"],
                )
            try:
                report, filters = run_prompt_report_template(
                    db,
                    template,
                    prompt_override=self._prompt_from_params(plan, params),
                    trigger="assistant",
                )
            except PromptInterpretationError as exc:
                return ActionResult(
                    message=self._format_interpretation_error(exc),
                    data={"status": "needs_prompt_adjustment", **exc.details},
                    success=False,
                    errors=["prompt_interpretation_failed"],
                )
            answer = self._answer_from_report(db, report)
            return ActionResult(
                message=answer["message"],
                data={
                    "report_id": report.id,
                    "report_url": f"/reports/redmine-deliveries?report_id={report.id}",
                    "status": report.status,
                    "template_id": template.id,
                    "template_name": template.name,
                    "total": answer["total"],
                    "items": answer["items"],
                    "filters": filters,
                },
            )

        return ActionResult(message="Acao de relatorio nao suportada.", data={}, success=False, errors=["unsupported_action"])

    def _format_interpretation_error(self, exc: PromptInterpretationError) -> str:
        details = exc.details or {}
        lines = [str(exc)]
        issues = details.get("possible_issues") or []
        if issues:
            lines.append("\nPontos que podem estar ambíguos:")
            lines.extend(f"- {item}" for item in issues[:4])
        identified = details.get("identified") or {}
        identified_parts = []
        if identified.get("project_ids"):
            identified_parts.append(f"projeto: {', '.join(identified['project_ids'])}")
        if identified.get("status_scope"):
            identified_parts.append(f"escopo de status: {identified['status_scope']}")
        if identified.get("columns"):
            identified_parts.append(f"colunas detectadas: {len(identified['columns'])}")
        if identified.get("filters"):
            identified_parts.append(f"filtros detectados: {len(identified['filters'])}")
        if identified_parts:
            lines.append("\nO que consegui identificar: " + "; ".join(identified_parts) + ".")
        suggestions = details.get("suggestions") or []
        if suggestions:
            lines.append("\nComo corrigir:")
            lines.extend(f"- {item}" for item in suggestions[:3])
        return "\n".join(lines)

    def _canonical_action(self, action: str | None) -> str:
        value = (action or "").strip().lower()
        if value in {
            "execute_report",
            "create_demands_report",
            "generate_demands_report",
            "generate_report",
            "run_redmine_report",
            "run_ai_report",
            "list_open_demands",
            "list_open_demands_by_user",
            "list_demands_by_user",
            "list_redmine_demands",
            "query_redmine_demands",
        }:
            return "run_report"
        if value in {"list_reports", "list_recent_reports", "recent_reports"}:
            return "list"
        return value

    def _prompt_from_params(self, plan: AssistantPlan, params: dict) -> str | None:
        explicit_text = str(params.get("text") or "").strip()
        if explicit_text:
            return explicit_text

        owner = str(params.get("owner") or params.get("assignee") or params.get("user") or "").strip()
        status = str(params.get("status") or "").strip().lower()
        if owner or status:
            status_text = "em aberto" if status in {"open", "opened", "aberto", "abertos"} else status
            parts = ["Liste as demandas do Redmine"]
            if status_text:
                parts.append(status_text)
            if owner:
                parts.append(f"do responsavel {owner}")
            return " ".join(parts) + "."

        return plan.summary_for_user or None

    def _answer_from_report(self, db: Session, report: Report) -> dict:
        rows = db.query(ReportRow).filter(ReportRow.report_id == report.id).order_by(ReportRow.id.asc()).limit(10).all()
        total = int((report.params_json or {}).get("records") or len(rows))
        items = [self._row_item(row) for row in rows]

        if total == 0:
            return {
                "total": 0,
                "items": [],
                "message": f"Nao encontrei demandas para essa consulta. O relatorio #{report.id} foi gerado sem registros.",
            }

        lines = [f"Encontrei {total} demanda{'s' if total != 1 else ''} para essa consulta."]
        for item in items[:5]:
            line = f"- #{item.get('id') or '-'}: {item.get('title') or 'Sem titulo'}"
            if item.get("assigned_to"):
                line += f" | responsavel: {item['assigned_to']}"
            if item.get("status"):
                line += f" | status: {item['status']}"
            if item.get("due_date"):
                line += f" | prevista: {item['due_date']}"
            lines.append(line)
        if total > len(items[:5]):
            lines.append(f"Mostrei as 5 primeiras. O relatorio #{report.id} contem a lista completa.")
        else:
            lines.append(f"Relatorio #{report.id} disponivel para detalhes e exportacao.")
        return {"total": total, "items": items, "message": "\n".join(lines)}

    def _row_item(self, row: ReportRow) -> dict:
        raw = row.raw_json or {}
        return {
            "id": row.source_ref or raw.get("id"),
            "title": raw.get("subject"),
            "assigned_to": raw.get("assigned_to"),
            "status": raw.get("status"),
            "due_date": raw.get("due_date"),
            "updated_on": raw.get("updated_on"),
            "project": raw.get("project"),
            "priority": raw.get("priority"),
            "url": row.source_url,
            "cliente": row.cliente,
            "sistema": row.sistema,
            "entrega": row.entrega,
        }

    def _default_template(self, db: Session) -> PromptReportTemplate | None:
        return (
            db.query(PromptReportTemplate)
            .filter(PromptReportTemplate.is_enabled.is_(True))
            .order_by(PromptReportTemplate.updated_at.desc(), PromptReportTemplate.id.desc())
            .first()
        )
