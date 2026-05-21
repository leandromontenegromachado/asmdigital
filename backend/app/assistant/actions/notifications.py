from __future__ import annotations

from sqlalchemy.orm import Session

from app.assistant.actions.base import ActionResult
from app.assistant.schemas import AssistantPlan
from app.models import Report, User
from app.services.notification_service import send_notifications_for_report


class NotificationsAction:
    domain = "notifications"

    def preview(self, db: Session, plan: AssistantPlan, user: User | None) -> dict:
        return {
            "title": "Notificacao",
            "action": plan.action,
            "params": plan.extracted_params,
            "missing_params": plan.missing_params,
            "impact": "O envio pode gerar notificacoes por e-mail, Teams ou canal interno conforme configuracao.",
        }

    def execute(self, db: Session, plan: AssistantPlan, user: User | None) -> ActionResult:
        if plan.action != "send":
            return ActionResult(message="Acao de notificacao nao suportada.", data={}, success=False, errors=["unsupported_action"])

        params = plan.extracted_params or {}
        report_id = params.get("report_id")
        report = None
        if report_id:
            report = db.query(Report).filter(Report.id == int(report_id)).first()
        elif params.get("source") == "last_report" or not report_id:
            report = db.query(Report).order_by(Report.generated_at.desc()).first()
        if not report:
            return ActionResult(message="Nao encontrei relatorio para enviar notificacoes.", data={}, success=False, errors=["report_not_found"])

        notifications = send_notifications_for_report(
            db,
            report,
            channel=params.get("channel"),
            requires_approval=bool(params.get("requires_approval", False)),
            simulation=bool(params.get("simulation", False)),
        )
        return ActionResult(
            message=f"Notificacoes processadas para o relatorio #{report.id}.",
            data={"report_id": report.id, "notifications": len(notifications), "ids": [item.id for item in notifications]},
        )
