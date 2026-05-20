from __future__ import annotations

import logging
import threading
import time

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.assistant_telegram_handler import process_telegram_update
from app.services.telegram_service import delete_telegram_webhook, get_telegram_updates

logger = logging.getLogger(__name__)

_stop_event = threading.Event()
_thread: threading.Thread | None = None


def start_telegram_polling() -> None:
    global _thread
    if not settings.assistant_telegram_enabled or not settings.telegram_polling_enabled:
        return
    if not settings.telegram_bot_token:
        logger.warning("Telegram polling enabled but TELEGRAM_BOT_TOKEN is not configured")
        return
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_polling_loop, name="telegram-polling", daemon=True)
    _thread.start()
    logger.info("Telegram polling started")


def stop_telegram_polling() -> None:
    _stop_event.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=10)


def _polling_loop() -> None:
    offset: int | None = None
    try:
        delete_telegram_webhook(drop_pending_updates=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to delete Telegram webhook before polling: %s", exc)

    while not _stop_event.is_set():
        try:
            updates = get_telegram_updates(offset=offset, timeout_seconds=25)
            for update in updates:
                update_id = update.get("update_id")
                try:
                    with SessionLocal() as db:
                        process_telegram_update(update, db)
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to process Telegram update %s", update_id)
                if isinstance(update_id, int):
                    offset = update_id + 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram polling error: %s", exc)
            _stop_event.wait(max(1, settings.telegram_polling_interval_seconds))
            continue

        _stop_event.wait(max(1, settings.telegram_polling_interval_seconds))
