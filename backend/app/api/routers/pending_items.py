from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.pending_items import (
    PendingItemAction,
    PendingItemCreate,
    PendingItemOut,
    PendingItemSummary,
    PendingItemUpdate,
)
from app.services.pending_item_service import PendingItemService, pending_item_to_out

router = APIRouter(prefix="/pending-items", tags=["pending-items"])


@router.get("", response_model=list[PendingItemOut])
def list_pending_items(
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    responsible_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    service = PendingItemService(db)
    items = service.list_items(
        status=status_filter,
        priority=priority,
        source_type=source_type,
        responsible_id=responsible_id,
        limit=limit,
    )
    return [pending_item_to_out(item) for item in items]


@router.post("", response_model=PendingItemOut, status_code=status.HTTP_201_CREATED)
def create_pending_item(
    payload: PendingItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = PendingItemService(db).create_item(payload, user)
    return pending_item_to_out(item)


@router.get("/dashboard/summary", response_model=PendingItemSummary)
def pending_items_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return PendingItemService(db).dashboard_summary()


@router.get("/{item_id}", response_model=PendingItemOut)
def get_pending_item(
    item_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    item = PendingItemService(db).get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Pending item not found")
    return pending_item_to_out(item)


@router.put("/{item_id}", response_model=PendingItemOut)
def update_pending_item(
    item_id: int,
    payload: PendingItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = PendingItemService(db)
    item = service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Pending item not found")
    return pending_item_to_out(service.update_item(item, payload, user))


@router.post("/{item_id}/comment", response_model=PendingItemOut)
def comment_pending_item(
    item_id: int,
    payload: PendingItemAction,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = PendingItemService(db)
    item = service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Pending item not found")
    return pending_item_to_out(service.comment_item(item, payload.note, user))


@router.post("/{item_id}/resolve", response_model=PendingItemOut)
def resolve_pending_item(
    item_id: int,
    payload: PendingItemAction | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = PendingItemService(db)
    item = service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Pending item not found")
    return pending_item_to_out(service.resolve_item(item, payload.note if payload else None, user))


@router.post("/{item_id}/ignore", response_model=PendingItemOut)
def ignore_pending_item(
    item_id: int,
    payload: PendingItemAction | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = PendingItemService(db)
    item = service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Pending item not found")
    return pending_item_to_out(service.ignore_item(item, payload.note if payload else None, user))


@router.post("/{item_id}/escalate", response_model=PendingItemOut)
def escalate_pending_item(
    item_id: int,
    payload: PendingItemAction | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = PendingItemService(db)
    item = service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Pending item not found")
    return pending_item_to_out(service.escalate_item(item, payload.note if payload else None, user))


@router.post("/{item_id}/reopen", response_model=PendingItemOut)
def reopen_pending_item(
    item_id: int,
    payload: PendingItemAction | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = PendingItemService(db)
    item = service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Pending item not found")
    return pending_item_to_out(service.reopen_item(item, payload.note if payload else None, user))
