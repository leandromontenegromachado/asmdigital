from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.management_events import (
    ManagementEventAction,
    ManagementEventCreate,
    ManagementEventOut,
    ManagementEventSummary,
    ManagementEventUpdate,
)
from app.services.management_event_service import ManagementEventService, management_event_to_out

router = APIRouter(prefix="/management-events", tags=["management-events"])


@router.get("", response_model=list[ManagementEventOut])
def list_management_events(
    status_filter: str | None = Query(default=None, alias="status"),
    event_type: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    service = ManagementEventService(db)
    events = service.list_events(
        status=status_filter,
        event_type=event_type,
        source_type=source_type,
        limit=limit,
    )
    return [management_event_to_out(event) for event in events]


@router.post("", response_model=ManagementEventOut, status_code=status.HTTP_201_CREATED)
def create_management_event(
    payload: ManagementEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event = ManagementEventService(db).create_event(payload, user)
    return management_event_to_out(event)


@router.get("/dashboard/summary", response_model=ManagementEventSummary)
def management_events_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return ManagementEventService(db).dashboard_summary()


@router.get("/{event_id}", response_model=ManagementEventOut)
def get_management_event(
    event_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    event = ManagementEventService(db).get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Management event not found")
    return management_event_to_out(event)


@router.put("/{event_id}", response_model=ManagementEventOut)
def update_management_event(
    event_id: int,
    payload: ManagementEventUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    service = ManagementEventService(db)
    event = service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Management event not found")
    return management_event_to_out(service.update_event(event, payload))


@router.post("/{event_id}/process", response_model=ManagementEventOut)
def process_management_event(
    event_id: int,
    payload: ManagementEventAction | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    service = ManagementEventService(db)
    event = service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Management event not found")
    return management_event_to_out(service.process_event(event, payload.note if payload else None))


@router.post("/{event_id}/ignore", response_model=ManagementEventOut)
def ignore_management_event(
    event_id: int,
    payload: ManagementEventAction | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    service = ManagementEventService(db)
    event = service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Management event not found")
    return management_event_to_out(service.ignore_event(event, payload.note if payload else None))
