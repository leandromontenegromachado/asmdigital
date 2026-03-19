from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Connector
from app.schemas.azure_devops import AzureDevOpsSnapshotOut
from app.services.azure_devops_service import AZURE_CONNECTOR_TYPES, get_azure_adapter, query_snapshot

router = APIRouter(prefix="/azure-devops", tags=["azure-devops"])


@router.get("/connectors/{connector_id}/snapshot", response_model=AzureDevOpsSnapshotOut)
def get_connector_snapshot(
    connector_id: int,
    project: str | None = Query(default=None),
    team: str | None = Query(default=None),
    area_path: str | None = Query(default=None),
    iteration_path: str | None = Query(default=None),
    top: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.type not in AZURE_CONNECTOR_TYPES:
        raise HTTPException(status_code=400, detail="Connector type must be Azure DevOps")

    try:
        return query_snapshot(
            connector,
            project=project,
            team=team,
            area_path=area_path,
            iteration_path=iteration_path,
            top=top,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to load Azure DevOps snapshot: {exc}") from exc


@router.post("/connectors/{connector_id}/test")
def test_connector(
    connector_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.type not in AZURE_CONNECTOR_TYPES:
        raise HTTPException(status_code=400, detail="Connector type must be Azure DevOps")
    try:
        adapter = get_azure_adapter(connector)
        return {"ok": True, "details": adapter.test_connection()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "details": {"error": str(exc)}}
