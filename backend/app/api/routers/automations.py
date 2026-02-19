from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Automation, AutomationRun
from app.schemas.automations import AutomationOut, AutomationRunOut, AutomationRunRequest, AutomationRunWithAutomation
from app.services.automation_service import ensure_default_automations, run_automation

router = APIRouter(prefix="/automations", tags=["automations"])


@router.get("", response_model=list[AutomationOut])
def list_automations(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    ensure_default_automations(db)
    return db.query(Automation).order_by(Automation.id.asc()).all()


@router.post("/{automation_id}/run", response_model=AutomationRunOut)
def run_automation_endpoint(
    automation_id: int,
    payload: AutomationRunRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    automation = db.query(Automation).filter(Automation.id == automation_id).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    run = run_automation(db, automation, simulation=payload.simulation)
    return run


@router.get("/runs", response_model=list[AutomationRunWithAutomation])
def list_runs(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    runs = (
        db.query(AutomationRun, Automation)
        .join(Automation, AutomationRun.automation_id == Automation.id)
        .order_by(AutomationRun.started_at.desc())
        .limit(50)
        .all()
    )
    return [
        AutomationRunWithAutomation(
            id=run.id,
            automation_id=run.automation_id,
            automation_name=automation.name,
            automation_key=automation.key,
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=run.status,
            summary_json=run.summary_json,
            error_text=run.error_text,
        )
        for run, automation in runs
    ]
