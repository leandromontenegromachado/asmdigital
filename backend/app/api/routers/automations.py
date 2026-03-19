from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Automation, AutomationRun
from app.scheduler import scheduler
from app.schemas.automations import (
    AutomationCreate,
    AutomationOut,
    AutomationRunOut,
    AutomationRunRequest,
    AutomationRunWithAutomation,
    AutomationUpdate,
)
from app.services.automation_service import (
    build_automation_key,
    ensure_default_automations,
    next_run_from_cron,
    run_automation,
    sync_automation_jobs,
    validate_cron_expression,
)

router = APIRouter(prefix="/automations", tags=["automations"])


def normalize_tasks(params_json: dict | None) -> dict:
    params = dict(params_json or {})
    raw_tasks = params.get("tasks")
    if not isinstance(raw_tasks, list):
        params["tasks"] = []
        return params

    params["tasks"] = [task.strip() for task in raw_tasks if isinstance(task, str) and task.strip()]
    return params


@router.get("", response_model=list[AutomationOut])
def list_automations(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    ensure_default_automations(db)
    return db.query(Automation).order_by(Automation.id.asc()).all()


@router.post("", response_model=AutomationOut)
def create_automation(
    payload: AutomationCreate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    ensure_default_automations(db)

    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    if payload.schedule_cron:
        try:
            validate_cron_expression(payload.schedule_cron)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {exc}") from exc

    existing_keys = {key for (key,) in db.query(Automation.key).all()}
    generated_key = build_automation_key(payload.name, existing_keys)
    params_json = normalize_tasks(payload.params_json)
    params_json.setdefault("simulation", True)

    automation = Automation(
        key=generated_key,
        name=payload.name.strip(),
        schedule_cron=(payload.schedule_cron or None),
        is_enabled=payload.is_enabled,
        params_json=params_json,
    )

    if automation.is_enabled and automation.schedule_cron:
        automation.next_run_at = next_run_from_cron(automation.schedule_cron)
    else:
        automation.next_run_at = None

    db.add(automation)
    db.commit()
    sync_automation_jobs(db, scheduler)
    db.refresh(automation)
    return automation


@router.put("/{automation_id}", response_model=AutomationOut)
def update_automation(
    automation_id: int,
    payload: AutomationUpdate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    automation = db.query(Automation).filter(Automation.id == automation_id).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")

    data = payload.model_dump(exclude_unset=True)
    if "schedule_cron" in data:
        try:
            validate_cron_expression(data["schedule_cron"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {exc}") from exc

    for key, value in data.items():
        setattr(automation, key, value)

    if "params_json" in data:
        automation.params_json = normalize_tasks(data["params_json"])
        automation.params_json.setdefault("simulation", True)

    if automation.is_enabled and automation.schedule_cron:
        automation.next_run_at = next_run_from_cron(automation.schedule_cron)
    else:
        automation.next_run_at = None

    db.commit()
    sync_automation_jobs(db, scheduler)
    db.refresh(automation)
    return automation


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
