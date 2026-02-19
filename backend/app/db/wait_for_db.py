import time
import logging

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)


def wait_for_db(max_attempts: int = 10, wait_seconds: int = 2) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("database_ready")
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("database_not_ready", extra={"attempt": attempt, "error": str(exc)})
            time.sleep(wait_seconds)
    raise RuntimeError("Database not available")


if __name__ == "__main__":
    wait_for_db()
