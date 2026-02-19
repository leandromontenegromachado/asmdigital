from fastapi import APIRouter, Depends, HTTPException, Query, status
from tenacity import RetryError
from sqlalchemy.orm import Session

from app.adapters.redmine import RedmineAdapter
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Connector
from app.schemas.connectors import ConnectorCreate, ConnectorOut, ConnectorTestResult, ConnectorUpdate, RedmineQueryOut

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("", response_model=list[ConnectorOut])
def list_connectors(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(Connector).order_by(Connector.id.desc()).all()


@router.post("", response_model=ConnectorOut, status_code=status.HTTP_201_CREATED)
def create_connector(
    payload: ConnectorCreate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    connector = Connector(**payload.model_dump())
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


@router.put("/{connector_id}", response_model=ConnectorOut)
def update_connector(
    connector_id: int,
    payload: ConnectorUpdate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(connector, key, value)
    db.commit()
    db.refresh(connector)
    return connector


@router.post("/{connector_id}/test", response_model=ConnectorTestResult)
def test_connector(
    connector_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.type != "redmine":
        return ConnectorTestResult(ok=True, message="Connector type does not require test")
    try:
        adapter = RedmineAdapter(
            base_url=connector.config_json.get("base_url"),
            api_key=connector.config_json.get("api_key"),
        )
        details = adapter.test_connection()
        return ConnectorTestResult(ok=True, message="Connection successful", details=details)
    except Exception as exc:  # noqa: BLE001
        return ConnectorTestResult(ok=False, message="Connection failed", details={"error": str(exc)})


@router.get("/{connector_id}/queries", response_model=list[RedmineQueryOut])
def list_redmine_queries(
    connector_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
    project_id: str | None = Query(default=None),
):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.type != "redmine":
        raise HTTPException(status_code=400, detail="Connector type does not support queries")
    try:
        adapter = RedmineAdapter(
            base_url=connector.config_json.get("base_url"),
            api_key=connector.config_json.get("api_key"),
        )
        queries = adapter.fetch_queries(project_id=project_id)
        return [
            RedmineQueryOut(
                id=int(item.get("id")),
                name=str(item.get("name", "")),
                is_public=item.get("is_public"),
            )
            for item in queries
            if item.get("id") is not None
        ]
    except RetryError as exc:
        root = exc.last_attempt.exception() if exc.last_attempt else exc
        raise HTTPException(status_code=502, detail=f"Failed to load queries: {root}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to load queries: {exc}") from exc
