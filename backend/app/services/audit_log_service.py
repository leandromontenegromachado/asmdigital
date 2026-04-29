from sqlalchemy.orm import Session

from app.models import AuditLog


class AuditLogService:
    def __init__(self, db: Session, actor_id: int | None = None):
        self.db = db
        self.actor_id = actor_id

    def register_action(self, action: str, entity_type: str, entity_id: int | None, old_value=None, new_value=None) -> None:
        self.db.add(AuditLog(
            user_id=self.actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
        ))
