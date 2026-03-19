import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.services.automation_service import ensure_default_automations, sync_automation_jobs
from app.services.prompt_report_service import sync_prompt_report_jobs
from app.modules.fala_ai.scheduler import sync_fala_ai_jobs
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def start_scheduler() -> None:
    if scheduler.running:
        return

    scheduler.start()

    with SessionLocal() as db:
        ensure_default_automations(db)
        sync_automation_jobs(db, scheduler)
        sync_prompt_report_jobs(db, scheduler)
        sync_fala_ai_jobs(db, scheduler)

    logger.info("scheduler_started")


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()
