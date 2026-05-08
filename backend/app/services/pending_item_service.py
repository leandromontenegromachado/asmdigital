from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Employee, ManagementEvent, PendingItem, PendingItemEvent, User
from app.schemas.pending_items import PendingItemCreate, PendingItemUpdate


class PendingItemService:
    def __init__(self, db: Session):
        self.db = db

    def list_items(
        self,
        status: str | None = None,
        priority: str | None = None,
        source_type: str | None = None,
        responsible_id: int | None = None,
        limit: int = 100,
    ) -> list[PendingItem]:
        query = self.db.query(PendingItem).options(joinedload(PendingItem.events))
        if status:
            query = query.filter(PendingItem.status == status)
        if priority:
            query = query.filter(PendingItem.priority == priority)
        if source_type:
            query = query.filter(PendingItem.source_type == source_type)
        if responsible_id:
            query = query.filter(PendingItem.responsible_id == responsible_id)
        return query.order_by(PendingItem.created_at.desc()).limit(min(max(limit, 1), 500)).all()

    def get_item(self, item_id: int) -> PendingItem | None:
        return (
            self.db.query(PendingItem)
            .options(joinedload(PendingItem.events))
            .filter(PendingItem.id == item_id)
            .first()
        )

    def create_item(self, payload: PendingItemCreate, actor: User) -> PendingItem:
        item = PendingItem(**payload.model_dump(), created_by=actor.id)
        self.db.add(item)
        self.db.flush()
        self._add_event(item, "created", None, item.status, None, actor)
        self.db.commit()
        self.db.refresh(item)
        return item

    def create_from_management_event(self, event: ManagementEvent, actor: User) -> PendingItem:
        responsible = event.responsible if isinstance(event.responsible, Employee) else None
        payload = {
            **(event.payload_json or {}),
            "management_event": {
                "id": event.id,
                "event_type": event.event_type,
                "source_type": event.source_type,
                "source_id": event.source_id,
                "severity": event.severity,
                "employee_id": event.responsible_id,
                "manager_id": responsible.manager_id if responsible else None,
            },
        }
        item = PendingItem(
            title=event.title,
            description=event.description,
            status="open",
            priority=event.severity or "medium",
            source_type=event.source_type,
            source_id=event.source_id,
            management_event_id=event.id,
            responsible_id=event.responsible_id,
            created_by=actor.id,
            payload_json=payload,
        )
        self.db.add(item)
        self.db.flush()
        self._add_event(
            item,
            "created_from_management_event",
            None,
            item.status,
            f"Pendencia criada a partir do evento gerencial #{event.id}.",
            actor,
        )
        event.status = "converted_to_pending"
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(self, item: PendingItem, payload: PendingItemUpdate, actor: User) -> PendingItem:
        data = payload.model_dump(exclude_unset=True)
        old_status = item.status
        for key, value in data.items():
            setattr(item, key, value)
        if "status" in data and data["status"] != old_status:
            self._apply_status_timestamps(item, data["status"])
            self._add_event(item, "status_changed", old_status, data["status"], data.get("resolution_note"), actor)
        self.db.commit()
        self.db.refresh(item)
        return item

    def comment_item(self, item: PendingItem, note: str | None, actor: User) -> PendingItem:
        self._add_event(item, "commented", item.status, item.status, note, actor)
        self.db.commit()
        self.db.refresh(item)
        return item

    def resolve_item(self, item: PendingItem, note: str | None, actor: User) -> PendingItem:
        return self._set_status(item, "resolved", "resolved", note, actor)

    def ignore_item(self, item: PendingItem, note: str | None, actor: User) -> PendingItem:
        return self._set_status(item, "ignored", "ignored", note, actor)

    def escalate_item(self, item: PendingItem, note: str | None, actor: User) -> PendingItem:
        return self._set_status(item, "escalated", "escalated", note, actor)

    def reopen_item(self, item: PendingItem, note: str | None, actor: User) -> PendingItem:
        return self._set_status(item, "open", "reopened", note, actor)

    def dashboard_summary(self) -> dict:
        total = self.db.query(func.count(PendingItem.id)).scalar() or 0
        status_counts = dict(
            self.db.query(PendingItem.status, func.count(PendingItem.id))
            .group_by(PendingItem.status)
            .all()
        )
        priority_counts = dict(
            self.db.query(PendingItem.priority, func.count(PendingItem.id))
            .group_by(PendingItem.priority)
            .all()
        )
        source_counts = dict(
            self.db.query(PendingItem.source_type, func.count(PendingItem.id))
            .group_by(PendingItem.source_type)
            .all()
        )
        return {
            "total": total,
            "open": status_counts.get("open", 0),
            "resolved": status_counts.get("resolved", 0),
            "ignored": status_counts.get("ignored", 0),
            "escalated": status_counts.get("escalated", 0),
            "reopened": status_counts.get("reopened", 0),
            "by_priority": {str(key): value for key, value in priority_counts.items() if key},
            "by_source_type": {str(key): value for key, value in source_counts.items() if key},
        }

    def _set_status(self, item: PendingItem, new_status: str, event_type: str, note: str | None, actor: User) -> PendingItem:
        old_status = item.status
        item.status = new_status
        item.resolution_note = note if note is not None else item.resolution_note
        self._apply_status_timestamps(item, new_status)
        self._add_event(item, event_type, old_status, new_status, note, actor)
        self.db.commit()
        self.db.refresh(item)
        return item

    def _apply_status_timestamps(self, item: PendingItem, status: str) -> None:
        now = datetime.now(timezone.utc)
        if status == "resolved":
            item.resolved_at = now
        elif status == "ignored":
            item.ignored_at = now
        elif status == "escalated":
            item.escalated_at = now
        elif status == "open":
            item.reopened_at = now

    def _add_event(
        self,
        item: PendingItem,
        event_type: str,
        old_status: str | None,
        new_status: str | None,
        note: str | None,
        actor: User,
    ) -> None:
        self.db.add(
            PendingItemEvent(
                pending_item_id=item.id,
                event_type=event_type,
                old_status=old_status,
                new_status=new_status,
                note=note,
                actor_id=actor.id,
                payload_json={},
            )
        )


def pending_item_event_to_out(event: PendingItemEvent):
    from app.schemas.pending_items import PendingItemEventOut

    actor = event.actor if isinstance(event.actor, User) else None
    return PendingItemEventOut(
        id=event.id,
        pending_item_id=event.pending_item_id,
        event_type=event.event_type,
        old_status=event.old_status,
        new_status=event.new_status,
        note=event.note,
        actor_id=event.actor_id,
        actor_name=actor.name if actor else None,
        payload_json=event.payload_json or {},
        created_at=event.created_at,
    )


def pending_item_to_out(item: PendingItem):
    from app.schemas.pending_items import PendingItemOut

    responsible = item.responsible if isinstance(item.responsible, Employee) else None
    creator = item.creator if isinstance(item.creator, User) else None
    events = sorted(item.events or [], key=lambda event: event.created_at)
    return PendingItemOut(
        id=item.id,
        title=item.title,
        description=item.description,
        status=item.status,
        priority=item.priority,
        source_type=item.source_type,
        source_id=item.source_id,
        management_event_id=item.management_event_id,
        responsible_id=item.responsible_id,
        responsible_name=responsible.name if responsible else None,
        created_by=item.created_by,
        created_by_name=creator.name if creator else None,
        due_date=item.due_date,
        payload_json=item.payload_json or {},
        resolved_at=item.resolved_at,
        ignored_at=item.ignored_at,
        escalated_at=item.escalated_at,
        reopened_at=item.reopened_at,
        resolution_note=item.resolution_note,
        created_at=item.created_at,
        updated_at=item.updated_at,
        events=[pending_item_event_to_out(event) for event in events],
    )
