from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Automation, AutomationRun


AUTOMATION_KEYS = [
    ("redmine_quarterly_report", "RelatÃƒÂ³rio trimestral Redmine"),
    ("fadpro_ihpe_check", "VerificaÃƒÂ§ÃƒÂ£o FADPRO/IHPE"),
    ("azure_epics_overdue", "Azure ÃƒÂ©picos vencidos"),
    ("hours_appropriation_watch", "ApropriaÃƒÂ§ÃƒÂ£o de horas (dedo-duro)"),
    ("ponto_abono_email", "Email do ponto Ã¢â€ â€™ gerar mensagem de prazo de abono"),
    ("teams_webhook_notify", "NotificaÃƒÂ§ÃƒÂ£o via Teams (Webhook, simulaÃƒÂ§ÃƒÂ£o)"),
]


def ensure_default_automations(db: Session) -> None:
    for key, name in AUTOMATION_KEYS:
        automation = db.query(Automation).filter(Automation.key == key).first()
        if automation:
            continue
        db.add(
            Automation(
                key=key,
                name=name,
                schedule_cron=None,
                is_enabled=True,
                params_json={"simulation": True},
            )
        )
    db.commit()


def run_automation(db: Session, automation: Automation, simulation: bool = True) -> AutomationRun:
    run = AutomationRun(
        automation_id=automation.id,
        status="running",
        summary_json={"simulation": simulation},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    summary: dict[str, Any] = {
        "message": "ExecuÃƒÂ§ÃƒÂ£o simulada concluÃƒÂ­da" if simulation else "ExecuÃƒÂ§ÃƒÂ£o concluÃƒÂ­da",
        "items": 1,
    }
    run.status = "success"
    run.summary_json = summary
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run
