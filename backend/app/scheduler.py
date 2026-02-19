import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.services.automation_service import ensure_default_automations
from app.services.prompt_report_service import sync_prompt_report_jobs
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def start_scheduler() -> None:
    if scheduler.running:
        return

    scheduler.start()

    with SessionLocal() as db:
        ensure_default_automations(db)
        sync_prompt_report_jobs(db, scheduler)

    logger.info("scheduler_started")


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()
