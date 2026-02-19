from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Connector, PromptReportTemplate, Report
from app.schemas.prompt_reports import (
    PromptReportRunOut,
    PromptReportRunRequest,
    PromptReportTemplateCreate,
    PromptReportTemplateOut,
    PromptReportTemplateUpdate,
)
from app.schemas.reports import ReportOut
from app.scheduler import scheduler
from app.services.prompt_report_service import (
    run_prompt_report_template,
    sync_prompt_report_jobs,
    validate_cron_expression,
)

router = APIRouter(prefix="/prompt-reports", tags=["prompt-reports"])


@router.get("", response_model=list[PromptReportTemplateOut])
def list_prompt_report_templates(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(PromptReportTemplate).order_by(PromptReportTemplate.updated_at.desc()).all()


@router.post("", response_model=PromptReportTemplateOut, status_code=status.HTTP_201_CREATED)
def create_prompt_report_template(
    payload: PromptReportTemplateCreate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    connector = db.query(Connector).filter(Connector.id == payload.connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    try:
        validate_cron_expression(payload.schedule_cron)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {exc}") from exc

    template = PromptReportTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    sync_prompt_report_jobs(db, scheduler)
    db.refresh(template)
    return template


@router.put("/{template_id}", response_model=PromptReportTemplateOut)
def update_prompt_report_template(
    template_id: int,
    payload: PromptReportTemplateUpdate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    template = db.query(PromptReportTemplate).filter(PromptReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    data = payload.model_dump(exclude_unset=True)
    if "connector_id" in data:
        connector = db.query(Connector).filter(Connector.id == data["connector_id"]).first()
        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")
    if "schedule_cron" in data:
        try:
            validate_cron_expression(data["schedule_cron"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {exc}") from exc

    for key, value in data.items():
        setattr(template, key, value)
    db.commit()
    db.refresh(template)
    sync_prompt_report_jobs(db, scheduler)
    db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt_report_template(
    template_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    template = db.query(PromptReportTemplate).filter(PromptReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(template)
    db.commit()
    sync_prompt_report_jobs(db, scheduler)


@router.post("/{template_id}/run", response_model=PromptReportRunOut)
def run_prompt_report_template_now(
    template_id: int,
    payload: PromptReportRunRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    template = db.query(PromptReportTemplate).filter(PromptReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        report, filters = run_prompt_report_template(db, template, prompt_override=payload.prompt_override, trigger="manual")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to run prompt report: {exc}") from exc

    serializable_filters = {
        **filters,
        "start_date": str(filters.get("start_date")),
        "end_date": str(filters.get("end_date")),
    }
    return PromptReportRunOut(report_id=report.id, status=report.status, extracted_filters=serializable_filters)


@router.get("/{template_id}/runs", response_model=list[ReportOut])
def list_prompt_report_runs(
    template_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
):
    template = db.query(PromptReportTemplate).filter(PromptReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return (
        db.query(Report)
        .filter(Report.params_json["template_id"].astext == str(template_id))
        .order_by(Report.generated_at.desc())
        .limit(limit)
        .all()
    )
