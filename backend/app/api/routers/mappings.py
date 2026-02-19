from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Mapping, Connector
from app.schemas.mappings import MappingOut, MappingUpdate, MappingPreviewResponse
from app.services.report_service import build_preview_tickets

router = APIRouter(prefix="/mappings", tags=["mappings"])


@router.get("", response_model=MappingOut | None)
def get_mapping(
    mapping_type: str = Query(..., alias="type"),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    mapping = db.query(Mapping).filter(Mapping.mapping_type == mapping_type).order_by(Mapping.updated_at.desc()).first()
    return mapping


@router.put("", response_model=MappingOut)
def upsert_mapping(
    payload: MappingUpdate,
    mapping_type: str = Query(..., alias="type"),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    mapping = (
        db.query(Mapping)
        .filter(Mapping.mapping_type == mapping_type)
        .filter(Mapping.connector_id == payload.connector_id)
        .first()
    )
    if not mapping:
        mapping = Mapping(mapping_type=mapping_type, connector_id=payload.connector_id, rules_json=payload.rules_json)
        db.add(mapping)
    else:
        mapping.rules_json = payload.rules_json
    db.commit()
    db.refresh(mapping)
    return mapping


@router.get("/preview", response_model=MappingPreviewResponse)
def preview_mapping(
    connector_id: int = Query(...),
    project_id: str = Query(...),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    tickets = build_preview_tickets(db, connector, project_id, limit=limit)
    return MappingPreviewResponse(tickets=tickets)
