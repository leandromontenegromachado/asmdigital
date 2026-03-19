from __future__ import annotations

from datetime import datetime, timezone
import logging
from uuid import uuid4

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import User
from app.modules.fala_ai.models import FalaAiLog, FalaAiReminder
from app.modules.fala_ai.service import build_daily_report, register_log
from app.modules.fala_ai.teams_integration import send_teams_message

logger = logging.getLogger(__name__)

JOB_PREFIX = "fala_ai:reminder:"
MISSING_CHECKIN_JOB_ID = "fala_ai:missing_checkins"


def _resolve_delivery_context(db) -> dict[str, str | None]:
    service_url = settings.fala_ai_teams_default_service_url
    conversation_id = settings.fala_ai_teams_default_conversation_id
    bot_id = settings.fala_ai_teams_default_bot_id
    channel_id = "teams" if settings.fala_ai_teams_default_conversation_id else None
    source = "settings"

    if service_url and conversation_id:
        return {
            "service_url": service_url,
            "conversation_id": conversation_id,
            "bot_id": bot_id,
            "channel_id": channel_id,
            "source": source,
        }

    latest_context_log = (
        db.query(FalaAiLog)
        .filter(FalaAiLog.evento == "teams_bot_context_received")
        .order_by(FalaAiLog.created_at.desc())
        .first()
    )
    payload = latest_context_log.payload if latest_context_log and isinstance(latest_context_log.payload, dict) else {}

    return {
        "service_url": str(payload.get("service_url")).strip() if payload.get("service_url") else None,
        "conversation_id": str(payload.get("conversation_id")).strip() if payload.get("conversation_id") else None,
        "bot_id": str(payload.get("bot_id")).strip() if payload.get("bot_id") else None,
        "channel_id": str(payload.get("channel_id")).strip() if payload.get("channel_id") else None,
        "source": "latest_context_log" if payload else "none",
    }


def _send_reminder(reminder_id: int) -> None:
    with SessionLocal() as db:
        reminder = db.query(FalaAiReminder).filter(FalaAiReminder.id == reminder_id, FalaAiReminder.ativo.is_(True)).first()
        if not reminder:
            return

        users = db.query(User).filter(User.is_active.is_(True)).all()
        payload = {
            "reminder_id": reminder.id,
            "message": reminder.mensagem,
            "users_targeted": len(users),
        }
        dispatch_id = str(uuid4())

        context = (
            {"service_url": None, "conversation_id": None, "bot_id": None, "channel_id": "webhook", "source": "webhook"}
            if settings.fala_ai_teams_outgoing_webhook
            else _resolve_delivery_context(db)
        )
        try:
            send_teams_message(
                message=reminder.mensagem,
                webhook_url=settings.fala_ai_teams_outgoing_webhook,
                bot_app_id=settings.fala_ai_teams_bot_app_id,
                bot_app_secret=settings.fala_ai_teams_bot_app_secret,
                bot_tenant_id=settings.fala_ai_teams_bot_tenant_id,
                service_url=context.get("service_url"),
                conversation_id=context.get("conversation_id"),
                bot_id=context.get("bot_id"),
            )
            payload["delivery_source"] = context.get("source")
        except RuntimeError:
            # Sem canal configurado; apenas registra log.
            payload["delivery_source"] = context.get("source")
            payload["delivery_skipped"] = True

        payload["dispatch_id"] = dispatch_id
        payload["sent_at"] = datetime.now(timezone.utc).isoformat()
        payload["service_url"] = context.get("service_url")
        payload["conversation_id"] = context.get("conversation_id")
        payload["bot_id"] = context.get("bot_id")
        payload["channel_id"] = context.get("channel_id")

        register_log(db, "reminder_sent", payload)


def _notify_missing_checkins() -> None:
    with SessionLocal() as db:
        today = datetime.now(timezone.utc).date()
        report = build_daily_report(db, target_date=today)
        if not report.missing_users:
            register_log(db, "missing_checkins_none", {"date": str(today)})
            return

        message = (
            "Fala ai... check-in pendente para: "
            + ", ".join(user.name for user in report.missing_users[:10])
        )
        context = (
            {"service_url": None, "conversation_id": None, "bot_id": None, "source": "webhook"}
            if settings.fala_ai_teams_outgoing_webhook
            else _resolve_delivery_context(db)
        )
        try:
            send_teams_message(
                message=message,
                webhook_url=settings.fala_ai_teams_outgoing_webhook,
                bot_app_id=settings.fala_ai_teams_bot_app_id,
                bot_app_secret=settings.fala_ai_teams_bot_app_secret,
                bot_tenant_id=settings.fala_ai_teams_bot_tenant_id,
                service_url=context.get("service_url"),
                conversation_id=context.get("conversation_id"),
                bot_id=context.get("bot_id"),
            )
            delivery_source = context.get("source")
        except RuntimeError:
            # Sem canal configurado; apenas registra log.
            delivery_source = context.get("source")

        register_log(
            db,
            "missing_checkins_report",
            {
                "date": str(today),
                "missing_total": len(report.missing_users),
                "checked_in_total": len(report.checked_in_users),
                "delivery_source": delivery_source,
            },
        )


def sync_fala_ai_jobs(db, scheduler: BaseScheduler) -> None:
    for job in scheduler.get_jobs():
        if job.id.startswith(JOB_PREFIX) or job.id == MISSING_CHECKIN_JOB_ID:
            scheduler.remove_job(job.id)

    reminders = db.query(FalaAiReminder).filter(FalaAiReminder.ativo.is_(True)).all()

    for reminder in reminders:
        cron = f"{reminder.horario.minute} {reminder.horario.hour} * * 1-5"
        trigger = CronTrigger.from_crontab(cron, timezone=timezone.utc)
        scheduler.add_job(
            _send_reminder,
            trigger=trigger,
            id=f"{JOB_PREFIX}{reminder.id}",
            args=[reminder.id],
            replace_existing=True,
        )

    if settings.fala_ai_missing_checkin_cron:
        trigger = CronTrigger.from_crontab(settings.fala_ai_missing_checkin_cron, timezone=timezone.utc)
        scheduler.add_job(
            _notify_missing_checkins,
            trigger=trigger,
            id=MISSING_CHECKIN_JOB_ID,
            replace_existing=True,
        )

    logger.info("fala_ai_jobs_synced", extra={"reminders": len(reminders)})


def send_reminder_now(reminder_id: int) -> None:
    _send_reminder(reminder_id)
