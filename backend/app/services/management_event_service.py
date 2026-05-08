from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Employee, ManagementEvent, User
from app.schemas.management_events import ManagementEventCreate, ManagementEventUpdate


class ManagementEventService:
    def __init__(self, db: Session):
        self.db = db

    def list_events(
        self,
        status: str | None = None,
        event_type: str | None = None,
        source_type: str | None = None,
        limit: int = 100,
    ) -> list[ManagementEvent]:
        query = self.db.query(ManagementEvent)
        if status:
            query = query.filter(ManagementEvent.status == status)
        if event_type:
            query = query.filter(ManagementEvent.event_type == event_type)
        if source_type:
            query = query.filter(ManagementEvent.source_type == source_type)
        return query.order_by(ManagementEvent.created_at.desc()).limit(min(max(limit, 1), 500)).all()

    def get_event(self, event_id: int) -> ManagementEvent | None:
        return self.db.query(ManagementEvent).filter(ManagementEvent.id == event_id).first()

    def create_event(self, payload: ManagementEventCreate, actor: User) -> ManagementEvent:
        event = ManagementEvent(**payload.model_dump(), created_by=actor.id)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def update_event(self, event: ManagementEvent, payload: ManagementEventUpdate) -> ManagementEvent:
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(event, key, value)
        self.db.commit()
        self.db.refresh(event)
        return event

    def process_event(self, event: ManagementEvent, note: str | None = None) -> ManagementEvent:
        event.status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        event.ignored_at = None
        if note is not None:
            event.resolution_note = note
        self.db.commit()
        self.db.refresh(event)
        return event

    def ignore_event(self, event: ManagementEvent, note: str | None = None) -> ManagementEvent:
        event.status = "ignored"
        event.ignored_at = datetime.now(timezone.utc)
        event.processed_at = None
        if note is not None:
            event.resolution_note = note
        self.db.commit()
        self.db.refresh(event)
        return event

    def dashboard_summary(self) -> dict:
        total = self.db.query(func.count(ManagementEvent.id)).scalar() or 0
        status_counts = dict(
            self.db.query(ManagementEvent.status, func.count(ManagementEvent.id))
            .group_by(ManagementEvent.status)
            .all()
        )
        severity_counts = dict(
            self.db.query(ManagementEvent.severity, func.count(ManagementEvent.id))
            .group_by(ManagementEvent.severity)
            .all()
        )
        type_counts = dict(
            self.db.query(ManagementEvent.event_type, func.count(ManagementEvent.id))
            .group_by(ManagementEvent.event_type)
            .all()
        )
        return {
            "total": total,
            "pending": status_counts.get("pending", 0),
            "processed": status_counts.get("processed", 0),
            "ignored": status_counts.get("ignored", 0),
            "by_severity": {str(key): value for key, value in severity_counts.items() if key},
            "by_event_type": {str(key): value for key, value in type_counts.items() if key},
        }


def management_event_to_out(event: ManagementEvent):
    from app.schemas.management_events import ManagementEventOut

    responsible = event.responsible if isinstance(event.responsible, Employee) else None
    creator = event.creator if isinstance(event.creator, User) else None
    return ManagementEventOut(
        id=event.id,
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        source_type=event.source_type,
        source_id=event.source_id,
        status=event.status,
        severity=event.severity,
        responsible_id=event.responsible_id,
        responsible_name=responsible.name if responsible else None,
        created_by=event.created_by,
        created_by_name=creator.name if creator else None,
        payload_json=event.payload_json or {},
        processed_at=event.processed_at,
        ignored_at=event.ignored_at,
        resolution_note=event.resolution_note,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )
