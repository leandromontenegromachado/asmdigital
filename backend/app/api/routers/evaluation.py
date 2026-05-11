import csv
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models import (
    AuditLog,
    AiFeedbackAnalysis,
    Employee,
    EvaluationAlert,
    EvaluationCycle,
    EvaluationImport,
    EvaluationImportRow,
    EvaluationScore,
    EmployeeRhData,
    PerformanceIndicator,
    PotentialScore,
    Review360,
    User,
)
from app.schemas.evaluation import (
    CalculateScoresOut,
    CalibrationPayload,
    DashboardOut,
    EmployeeCreate,
    EmployeeOut,
    EmployeeUpdate,
    AiAnalysisReviewPayload,
    AiFeedbackAnalysisOut,
    EvaluationAlertOut,
    EvaluationCycleCreate,
    EvaluationCycleOut,
    EvaluationCycleStatusUpdate,
    EvaluationCycleUpdate,
    EvaluationScoreOut,
    EvaluationImportOut,
    EvaluationImportRowOut,
    FinalListRowOut,
    ImportColumnMappingPayload,
    ImportConfirmOut,
    ImportValidationOut,
    IndicatorOut,
    IndicatorPayload,
    OperationalImportOut,
    EmployeeRhDataOut,
    PotentialOut,
    PotentialPayload,
    Review360Create,
    Review360Out,
    PreliminaryReportOut,
)
from app.services.ai_feedback_analysis_service import AiFeedbackAnalysisService
from app.services.csv_evaluation_import_service import CsvEvaluationImportService
from app.services.evaluation_operational_import_service import EvaluationOperationalImportService
from app.services.evaluation_scoring_service import EvaluationScoringService

router = APIRouter(tags=["evaluation"])


def _audit(db: Session, actor: User, action: str, entity_type: str, entity_id: int | None, old_value=None, new_value=None) -> None:
    db.add(AuditLog(
        user_id=actor.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
    ))


def _cycle(db: Session, cycle_id: int) -> EvaluationCycle:
    cycle = db.query(EvaluationCycle).filter(EvaluationCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo avaliativo nao encontrado")
    return cycle


def _employee(db: Session, employee_id: int) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador nao encontrado")
    return employee


def _ensure_not_finalized(cycle: EvaluationCycle) -> None:
    if cycle.status == "FINALIZADO":
        raise HTTPException(status_code=400, detail="Ciclo finalizado nao permite alteracao")


def _normalize(value: float | None) -> float | None:
    return EvaluationScoringService.normalize_score(value)


def _import_record(db: Session, cycle_id: int, import_id: int) -> EvaluationImport:
    row = db.query(EvaluationImport).filter(EvaluationImport.id == import_id, EvaluationImport.cycle_id == cycle_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Importacao nao encontrada")
    return row


def _employee_out(employee: Employee) -> EmployeeOut:
    return EmployeeOut(
        id=employee.id,
        name=employee.name,
        email=employee.email,
        teams_user_id=employee.teams_user_id,
        matricula=employee.matricula,
        cargo=employee.cargo,
        setor=employee.setor,
        department=employee.department,
        position=employee.position,
        manager_id=employee.manager_id,
        manager_name=employee.manager.name if employee.manager else None,
        active=employee.active,
        recebe_notificacao=employee.recebe_notificacao,
        participa_avaliacao=employee.participa_avaliacao,
        canal_preferencial=employee.canal_preferencial,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
    )


def _alert_out(alert: EvaluationAlert) -> EvaluationAlertOut:
    return EvaluationAlertOut(
        id=alert.id,
        cycle_id=alert.cycle_id,
        employee_id=alert.employee_id,
        employee_name=alert.employee.name if alert.employee else None,
        alert_type=alert.alert_type,
        message=alert.message,
        severity=alert.severity,
        created_at=alert.created_at,
        resolved_at=alert.resolved_at,
        resolved_by=alert.resolved_by,
    )


def _rh_out(row: EmployeeRhData) -> EmployeeRhDataOut:
    return EmployeeRhDataOut(
        id=row.id,
        cycle_id=row.cycle_id,
        employee_id=row.employee_id,
        employee_name=row.employee.name if row.employee else None,
        career_level=row.career_level,
        last_merit_date=row.last_merit_date,
        admission_date=row.admission_date,
        is_level_one_separate_budget=row.is_level_one_separate_budget,
        eligible_for_merit=row.eligible_for_merit,
        eligibility_reason=row.eligibility_reason,
    )


def _score_out(score: EvaluationScore, alerts: list[EvaluationAlert] | None = None) -> EvaluationScoreOut:
    employee = score.employee
    return EvaluationScoreOut(
        id=score.id,
        cycle_id=score.cycle_id,
        employee_id=score.employee_id,
        employee_name=employee.name,
        department=employee.department,
        position=employee.position,
        manager_name=employee.manager.name if employee.manager else None,
        performance_score=score.performance_score,
        behavior_score=score.behavior_score,
        potential_score=score.potential_score,
        preliminary_final_score=score.preliminary_final_score,
        suggested_category=score.suggested_category,
        final_category=score.final_category,
        nine_box_position=score.nine_box_position,
        calibration_justification=score.calibration_justification,
        calibrated_by=score.calibrated_by,
        calibrated_at=score.calibrated_at,
        alerts=[_alert_out(alert) for alert in alerts or []],
    )


def _import_out(row: EvaluationImport) -> EvaluationImportOut:
    return EvaluationImportOut(
        id=row.id,
        cycle_id=row.cycle_id,
        file_name=row.file_name,
        status=row.status,
        uploaded_by=row.uploaded_by,
        uploaded_at=row.uploaded_at,
        column_mapping_json=row.column_mapping_json,
        total_rows=row.total_rows,
        valid_rows=row.valid_rows,
        invalid_rows=row.invalid_rows,
        error_message=row.error_message,
        headers=CsvEvaluationImportService.headers(row),
    )


def _import_row_out(row: EvaluationImportRow) -> EvaluationImportRowOut:
    return EvaluationImportRowOut(
        id=row.id,
        import_id=row.import_id,
        row_number=row.row_number,
        raw_data_json=row.raw_data_json,
        normalized_data_json=row.normalized_data_json,
        status=row.status,
        error_message=row.error_message,
    )


def _ai_out(row: AiFeedbackAnalysis) -> AiFeedbackAnalysisOut:
    return AiFeedbackAnalysisOut(
        id=row.id,
        cycle_id=row.cycle_id,
        employee_id=row.employee_id,
        employee_name=row.employee.name if row.employee else None,
        status=row.status,
        summary=row.summary,
        strengths_json=row.strengths_json,
        attention_points_json=row.attention_points_json,
        recurring_themes_json=row.recurring_themes_json,
        qualitative_alerts_json=row.qualitative_alerts_json,
        suggested_feedback=row.suggested_feedback,
        model_used=row.model_used,
        raw_response_json=row.raw_response_json,
        error_message=row.error_message,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
    )


@router.get("/evaluation-cycles", response_model=list[EvaluationCycleOut])
@router.get("/evaluation/cycles", response_model=list[EvaluationCycleOut])
def list_cycles(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return db.query(EvaluationCycle).order_by(EvaluationCycle.id.desc()).all()


@router.post("/evaluation-cycles", response_model=EvaluationCycleOut, status_code=status.HTTP_201_CREATED)
@router.post("/evaluation/cycles", response_model=EvaluationCycleOut, status_code=status.HTTP_201_CREATED)
def create_cycle(payload: EvaluationCycleCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    total = payload.performance_weight + payload.behavior_weight + payload.potential_weight
    if abs(total - 1.0) > 0.0001:
        raise HTTPException(status_code=400, detail="A soma dos pesos deve ser 1.0")
    cycle = EvaluationCycle(**payload.model_dump())
    db.add(cycle)
    db.flush()
    _audit(db, admin, "CREATE_CYCLE", "evaluation_cycles", cycle.id, None, payload.model_dump(mode="json"))
    db.commit()
    db.refresh(cycle)
    return cycle


@router.get("/evaluation-cycles/{cycle_id}", response_model=EvaluationCycleOut)
@router.get("/evaluation/cycles/{cycle_id}", response_model=EvaluationCycleOut)
def get_cycle(cycle_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return _cycle(db, cycle_id)


@router.put("/evaluation-cycles/{cycle_id}", response_model=EvaluationCycleOut)
@router.put("/evaluation/cycles/{cycle_id}", response_model=EvaluationCycleOut)
def update_cycle(cycle_id: int, payload: EvaluationCycleUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    _ensure_not_finalized(cycle)
    data = payload.model_dump(exclude_unset=True)
    old = {key: getattr(cycle, key) for key in data}
    for key, value in data.items():
        setattr(cycle, key, value)
    _audit(db, admin, "UPDATE_CYCLE", "evaluation_cycles", cycle.id, old, data)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.patch("/evaluation-cycles/{cycle_id}/status", response_model=EvaluationCycleOut)
@router.patch("/evaluation/cycles/{cycle_id}/status", response_model=EvaluationCycleOut)
def update_cycle_status(cycle_id: int, payload: EvaluationCycleStatusUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    old = {"status": cycle.status}
    cycle.status = payload.status
    action = "FINALIZE_CYCLE" if payload.status == "FINALIZADO" else "UPDATE_CYCLE_STATUS"
    _audit(db, admin, action, "evaluation_cycles", cycle.id, old, {"status": cycle.status})
    db.commit()
    db.refresh(cycle)
    return cycle


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(
    department: str | None = Query(default=None),
    manager_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    query = db.query(Employee)
    if department:
        query = query.filter(Employee.department == department)
    if manager_id:
        query = query.filter(Employee.manager_id == manager_id)
    return [_employee_out(employee) for employee in query.order_by(Employee.name.asc()).all()]


@router.post("/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    data = payload.model_dump()
    data["email"] = data["email"].strip().lower()
    if data.get("matricula"):
        data["matricula"] = str(data["matricula"]).strip() or None
    if db.query(Employee).filter(Employee.email == data["email"]).first():
        raise HTTPException(status_code=400, detail="Ja existe funcionario com este email")
    if data.get("matricula") and db.query(Employee).filter(Employee.matricula == data["matricula"]).first():
        raise HTTPException(status_code=400, detail="Ja existe funcionario com esta matricula")
    if data.get("setor") and not data.get("department"):
        data["department"] = data["setor"]
    if data.get("cargo") and not data.get("position"):
        data["position"] = data["cargo"]
    employee = Employee(**data)
    db.add(employee)
    db.flush()
    _audit(db, admin, "CREATE_EMPLOYEE", "employees", employee.id, None, payload.model_dump(mode="json"))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Nao foi possivel salvar: email ou matricula ja cadastrado") from exc
    db.refresh(employee)
    return _employee_out(employee)


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return _employee_out(_employee(db, employee_id))


@router.put("/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, payload: EmployeeUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    employee = _employee(db, employee_id)
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        data["email"] = data["email"].strip().lower()
        if db.query(Employee).filter(Employee.email == data["email"], Employee.id != employee_id).first():
            raise HTTPException(status_code=400, detail="Ja existe funcionario com este email")
    if "matricula" in data and data["matricula"]:
        data["matricula"] = str(data["matricula"]).strip() or None
        if data["matricula"] and db.query(Employee).filter(Employee.matricula == data["matricula"], Employee.id != employee_id).first():
            raise HTTPException(status_code=400, detail="Ja existe funcionario com esta matricula")
    if data.get("manager_id") == employee_id:
        raise HTTPException(status_code=400, detail="Funcionario nao pode ser gestor dele mesmo")
    old = {key: getattr(employee, key) for key in data}
    for key, value in data.items():
        setattr(employee, key, value)
    if "setor" in data and "department" not in data:
        employee.department = data["setor"]
    if "cargo" in data and "position" not in data:
        employee.position = data["cargo"]
    _audit(db, admin, "UPDATE_EMPLOYEE", "employees", employee.id, old, data)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Nao foi possivel salvar: email ou matricula ja cadastrado") from exc
    db.refresh(employee)
    return _employee_out(employee)


@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    employee = _employee(db, employee_id)
    _audit(db, admin, "DELETE_EMPLOYEE", "employees", employee.id, {"name": employee.name, "email": employee.email}, None)
    db.query(Employee).filter(Employee.manager_id == employee_id).update({"manager_id": None})
    db.delete(employee)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Nao foi possivel excluir: funcionario possui historico vinculado. Desative o cadastro em vez de excluir.",
        ) from exc
    return None


@router.post("/evaluation-cycles/{cycle_id}/imports", response_model=EvaluationImportOut, status_code=status.HTTP_201_CREATED)
def upload_evaluation_csv(cycle_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    _ensure_not_finalized(cycle)
    try:
        import_record = CsvEvaluationImportService(db, actor_id=admin.id).upload_csv(cycle_id, file.filename or "evaluation.csv", file.file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(import_record)
    return _import_out(import_record)


@router.get("/evaluation-cycles/{cycle_id}/imports", response_model=list[EvaluationImportOut])
def list_evaluation_imports(cycle_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    _cycle(db, cycle_id)
    return [_import_out(row) for row in db.query(EvaluationImport).filter(EvaluationImport.cycle_id == cycle_id).order_by(EvaluationImport.id.desc()).all()]


@router.post("/evaluation-cycles/{cycle_id}/imports/{import_id}/map-columns", response_model=EvaluationImportOut)
def map_import_columns(cycle_id: int, import_id: int, payload: ImportColumnMappingPayload, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    _ensure_not_finalized(cycle)
    import_record = _import_record(db, cycle_id, import_id)
    try:
        CsvEvaluationImportService(db, actor_id=admin.id).map_columns(import_record, payload.mapping)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(import_record)
    return _import_out(import_record)


@router.post("/evaluation-cycles/{cycle_id}/imports/{import_id}/validate", response_model=ImportValidationOut)
def validate_import(cycle_id: int, import_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    _ensure_not_finalized(cycle)
    import_record = _import_record(db, cycle_id, import_id)
    try:
        CsvEvaluationImportService(db, actor_id=admin.id).validate_import(import_record)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(import_record)
    errors = [row for row in import_record.rows if row.status == "ERROR"]
    return ImportValidationOut(
        import_id=import_record.id,
        status=import_record.status,
        total_rows=import_record.total_rows,
        valid_rows=import_record.valid_rows,
        invalid_rows=import_record.invalid_rows,
        errors=[_import_row_out(row) for row in errors],
    )


@router.post("/evaluation-cycles/{cycle_id}/imports/{import_id}/confirm", response_model=ImportConfirmOut)
def confirm_import(cycle_id: int, import_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    _ensure_not_finalized(cycle)
    import_record = _import_record(db, cycle_id, import_id)
    try:
        summary = CsvEvaluationImportService(db, actor_id=admin.id).confirm_import(import_record)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return ImportConfirmOut(import_id=import_record.id, imported_rows=summary.imported_rows, created_reviews=summary.created_reviews)


@router.get("/evaluation-cycles/{cycle_id}/imports/{import_id}/errors", response_model=list[EvaluationImportRowOut])
def import_errors(cycle_id: int, import_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    _cycle(db, cycle_id)
    _import_record(db, cycle_id, import_id)
    rows = (
        db.query(EvaluationImportRow)
        .filter(EvaluationImportRow.import_id == import_id, EvaluationImportRow.status == "ERROR")
        .order_by(EvaluationImportRow.row_number.asc())
        .all()
    )
    return [_import_row_out(row) for row in rows]


@router.get("/evaluation-cycles/{cycle_id}/indicators", response_model=list[IndicatorOut])
def list_indicators(cycle_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    _cycle(db, cycle_id)
    rows = (
        db.query(PerformanceIndicator)
        .filter(PerformanceIndicator.cycle_id == cycle_id)
        .order_by(PerformanceIndicator.employee_id.asc())
        .all()
    )
    return [
        IndicatorOut(
            id=row.id,
            cycle_id=row.cycle_id,
            employee_id=row.employee_id,
            employee_name=row.employee.name if row.employee else None,
            rpm_original=row.rpm_original,
            rpm_normalized=row.rpm_normalized,
            ihpe_original=row.ihpe_original,
            ihpe_normalized=row.ihpe_normalized,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.get("/evaluation-cycles/{cycle_id}/rh-data", response_model=list[EmployeeRhDataOut])
def list_rh_data(cycle_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    _cycle(db, cycle_id)
    return [
        _rh_out(row)
        for row in db.query(EmployeeRhData).filter(EmployeeRhData.cycle_id == cycle_id).join(Employee).order_by(Employee.name.asc()).all()
    ]


@router.post("/evaluation-cycles/{cycle_id}/operational-imports/rpm", response_model=OperationalImportOut)
def import_rpm(cycle_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    _ensure_not_finalized(cycle)
    summary = EvaluationOperationalImportService(db, actor_id=admin.id).import_rpm(cycle_id, file.filename, file.file.read())
    _audit(db, admin, "IMPORT_EVALUATION_RPM", "evaluation_cycles", cycle_id, None, summary.__dict__)
    db.flush()
    EvaluationScoringService(db, actor_id=admin.id).calculate_cycle(cycle)
    db.commit()
    return OperationalImportOut(**summary.__dict__)


@router.post("/evaluation-cycles/{cycle_id}/operational-imports/ihpe", response_model=OperationalImportOut)
def import_ihpe(cycle_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    _ensure_not_finalized(cycle)
    summary = EvaluationOperationalImportService(db, actor_id=admin.id).import_ihpe(cycle_id, file.filename, file.file.read())
    _audit(db, admin, "IMPORT_EVALUATION_IHPE", "evaluation_cycles", cycle_id, None, summary.__dict__)
    db.flush()
    EvaluationScoringService(db, actor_id=admin.id).calculate_cycle(cycle)
    db.commit()
    return OperationalImportOut(**summary.__dict__)


@router.post("/evaluation-cycles/{cycle_id}/operational-imports/rh", response_model=OperationalImportOut)
def import_rh(cycle_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    _ensure_not_finalized(cycle)
    summary = EvaluationOperationalImportService(db, actor_id=admin.id).import_rh(cycle_id, file.filename, file.file.read())
    _audit(db, admin, "IMPORT_EVALUATION_RH", "evaluation_cycles", cycle_id, None, summary.__dict__)
    db.commit()
    return OperationalImportOut(**summary.__dict__)


@router.post("/evaluation-cycles/{cycle_id}/employees/{employee_id}/indicators", response_model=IndicatorOut)
@router.put("/evaluation-cycles/{cycle_id}/employees/{employee_id}/indicators", response_model=IndicatorOut)
def upsert_indicator(cycle_id: int, employee_id: int, payload: IndicatorPayload, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    _ensure_not_finalized(cycle)
    _employee(db, employee_id)
    row = (
        db.query(PerformanceIndicator)
        .filter(PerformanceIndicator.cycle_id == cycle_id, PerformanceIndicator.employee_id == employee_id)
        .first()
    )
    if not row:
        row = PerformanceIndicator(cycle_id=cycle_id, employee_id=employee_id)
        db.add(row)
        action = "CREATE_INDICATORS"
    else:
        action = "UPDATE_INDICATORS"
    old = {"rpm_original": row.rpm_original, "ihpe_original": row.ihpe_original}
    row.rpm_original = payload.rpm_original
    row.rpm_normalized = _normalize(payload.rpm_original)
    row.ihpe_original = payload.ihpe_original
    row.ihpe_normalized = _normalize(payload.ihpe_original)
    _audit(db, admin, action, "performance_indicators", row.id, old, payload.model_dump(mode="json"))
    db.commit()
    db.refresh(row)
    return IndicatorOut(
        id=row.id,
        cycle_id=row.cycle_id,
        employee_id=row.employee_id,
        employee_name=row.employee.name if row.employee else None,
        rpm_original=row.rpm_original,
        rpm_normalized=row.rpm_normalized,
        ihpe_original=row.ihpe_original,
        ihpe_normalized=row.ihpe_normalized,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/evaluation-cycles/{cycle_id}/reviews", response_model=list[Review360Out])
def list_reviews(cycle_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    _cycle(db, cycle_id)
    return [_review_out(row) for row in db.query(Review360).filter(Review360.cycle_id == cycle_id).order_by(Review360.id.desc()).all()]


def _review_out(row: Review360) -> Review360Out:
    return Review360Out(
        id=row.id,
        cycle_id=row.cycle_id,
        import_id=row.import_id,
        import_row_id=row.import_row_id,
        evaluator_id=row.evaluator_id,
        evaluator_email=row.evaluator_email or (row.evaluator.email if row.evaluator else None),
        evaluator_name=row.evaluator_name or (row.evaluator.name if row.evaluator else None),
        evaluated_id=row.evaluated_id,
        evaluated_email=row.evaluated_email or (row.evaluated.email if row.evaluated else None),
        evaluated_name=row.evaluated_name or (row.evaluated.name if row.evaluated else None),
        relation_type=row.relation_type,
        score=row.score,
        general_score=row.general_score,
        communication_score=row.communication_score,
        teamwork_score=row.teamwork_score,
        commitment_score=row.commitment_score,
        autonomy_score=row.autonomy_score,
        quality_score=row.quality_score,
        problem_solving_score=row.problem_solving_score,
        strengths_comment=row.strengths_comment,
        improvement_comment=row.improvement_comment,
        general_comment=row.general_comment,
        comment=row.comment,
        submitted_at=row.submitted_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/evaluation-cycles/{cycle_id}/reviews", response_model=Review360Out, status_code=status.HTTP_201_CREATED)
def create_review(cycle_id: int, payload: Review360Create, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    _ensure_not_finalized(cycle)
    if payload.evaluator_id:
        _employee(db, payload.evaluator_id)
    _employee(db, payload.evaluated_id)
    data = payload.model_dump()
    score = data.get("general_score") if data.get("general_score") is not None else data.get("score")
    if score is None:
        competence_scores = [
            data.get(field)
            for field in ["communication_score", "teamwork_score", "commitment_score", "autonomy_score", "quality_score", "problem_solving_score"]
            if data.get(field) is not None
        ]
        if not competence_scores:
            raise HTTPException(status_code=400, detail="Informe general_score, score ou nota por competencia")
        score = round(sum(competence_scores) / len(competence_scores), 2)
    data["score"] = score
    data["general_score"] = score
    row = Review360(cycle_id=cycle_id, **data)
    db.add(row)
    db.flush()
    _audit(db, admin, "CREATE_REVIEW_360", "reviews_360", row.id, None, payload.model_dump(mode="json"))
    db.commit()
    db.refresh(row)
    return _review_out(row)


@router.get("/evaluation-cycles/{cycle_id}/employees/{employee_id}/reviews", response_model=list[Review360Out])
def employee_reviews(cycle_id: int, employee_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    _cycle(db, cycle_id)
    _employee(db, employee_id)
    return [_review_out(row) for row in db.query(Review360).filter(Review360.cycle_id == cycle_id, Review360.evaluated_id == employee_id).all()]


@router.post("/evaluation-cycles/{cycle_id}/employees/{employee_id}/potential", response_model=PotentialOut)
@router.put("/evaluation-cycles/{cycle_id}/employees/{employee_id}/potential", response_model=PotentialOut)
def upsert_potential(cycle_id: int, employee_id: int, payload: PotentialPayload, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    _ensure_not_finalized(cycle)
    _employee(db, employee_id)
    row = db.query(PotentialScore).filter(PotentialScore.cycle_id == cycle_id, PotentialScore.employee_id == employee_id).first()
    if not row:
        row = PotentialScore(cycle_id=cycle_id, employee_id=employee_id, created_by=admin.id)
        db.add(row)
        action = "CREATE_POTENTIAL"
    else:
        action = "UPDATE_POTENTIAL"
    old = {"score": row.score, "comment": row.comment}
    row.score = payload.score
    row.comment = payload.comment
    row.created_by = admin.id
    _audit(db, admin, action, "potential_scores", row.id, old, payload.model_dump(mode="json"))
    db.commit()
    db.refresh(row)
    return _potential_out(row)


@router.get("/evaluation-cycles/{cycle_id}/employees/{employee_id}/potential", response_model=PotentialOut)
def get_potential(cycle_id: int, employee_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    row = db.query(PotentialScore).filter(PotentialScore.cycle_id == cycle_id, PotentialScore.employee_id == employee_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Potencial nao encontrado")
    return _potential_out(row)


def _potential_out(row: PotentialScore) -> PotentialOut:
    return PotentialOut(
        id=row.id,
        cycle_id=row.cycle_id,
        employee_id=row.employee_id,
        employee_name=row.employee.name if row.employee else None,
        score=row.score,
        comment=row.comment,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/evaluation-cycles/{cycle_id}/calculate-scores", response_model=CalculateScoresOut)
def calculate_scores(cycle_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    if cycle.status == "FINALIZADO":
        raise HTTPException(status_code=400, detail="Ciclo finalizado nao permite calculo")
    summary = EvaluationScoringService(db, actor_id=admin.id).calculate_cycle(cycle)
    return CalculateScoresOut(cycle_id=cycle_id, processed=summary.processed, incomplete=summary.incomplete, alerts_generated=summary.alerts_generated)


@router.get("/evaluation-cycles/{cycle_id}/scores", response_model=list[EvaluationScoreOut])
def list_scores(cycle_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    _cycle(db, cycle_id)
    alerts = db.query(EvaluationAlert).filter(EvaluationAlert.cycle_id == cycle_id, EvaluationAlert.resolved_at.is_(None)).all()
    by_employee: dict[int, list[EvaluationAlert]] = {}
    for alert in alerts:
        by_employee.setdefault(alert.employee_id, []).append(alert)
    scores = db.query(EvaluationScore).filter(EvaluationScore.cycle_id == cycle_id).join(Employee).order_by(Employee.name.asc()).all()
    return [_score_out(score, by_employee.get(score.employee_id, [])) for score in scores]


@router.get("/evaluation-cycles/{cycle_id}/employees/{employee_id}/score", response_model=EvaluationScoreOut)
def employee_score(cycle_id: int, employee_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    score = db.query(EvaluationScore).filter(EvaluationScore.cycle_id == cycle_id, EvaluationScore.employee_id == employee_id).first()
    if not score:
        raise HTTPException(status_code=404, detail="Score nao encontrado")
    alerts = db.query(EvaluationAlert).filter(EvaluationAlert.cycle_id == cycle_id, EvaluationAlert.employee_id == employee_id, EvaluationAlert.resolved_at.is_(None)).all()
    return _score_out(score, alerts)


@router.post("/evaluation-cycles/{cycle_id}/run-ai-analysis", response_model=list[AiFeedbackAnalysisOut])
def run_cycle_ai_analysis(cycle_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    if cycle.status == "FINALIZADO":
        raise HTTPException(status_code=400, detail="Ciclo finalizado nao permite reprocessar IA")
    rows = AiFeedbackAnalysisService(db, actor_id=admin.id).run_analysis_for_cycle(cycle)
    db.commit()
    for row in rows:
        db.refresh(row)
    return [_ai_out(row) for row in rows]


@router.post("/evaluation-cycles/{cycle_id}/employees/{employee_id}/run-ai-analysis", response_model=AiFeedbackAnalysisOut)
def run_employee_ai_analysis(cycle_id: int, employee_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    if cycle.status == "FINALIZADO":
        raise HTTPException(status_code=400, detail="Ciclo finalizado nao permite reprocessar IA")
    employee = _employee(db, employee_id)
    row = AiFeedbackAnalysisService(db, actor_id=admin.id).run_analysis_for_employee(cycle, employee)
    db.commit()
    db.refresh(row)
    return _ai_out(row)


@router.get("/evaluation-cycles/{cycle_id}/employees/{employee_id}/ai-analysis", response_model=AiFeedbackAnalysisOut)
def get_employee_ai_analysis(cycle_id: int, employee_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    _cycle(db, cycle_id)
    _employee(db, employee_id)
    row = db.query(AiFeedbackAnalysis).filter(AiFeedbackAnalysis.cycle_id == cycle_id, AiFeedbackAnalysis.employee_id == employee_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Analise IA nao encontrada")
    return _ai_out(row)


@router.patch("/evaluation-cycles/{cycle_id}/employees/{employee_id}/ai-analysis/review", response_model=AiFeedbackAnalysisOut)
def review_employee_ai_analysis(cycle_id: int, employee_id: int, payload: AiAnalysisReviewPayload, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _cycle(db, cycle_id)
    _employee(db, employee_id)
    row = db.query(AiFeedbackAnalysis).filter(AiFeedbackAnalysis.cycle_id == cycle_id, AiFeedbackAnalysis.employee_id == employee_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Analise IA nao encontrada")
    if payload.reviewed:
        row.status = "REVIEWED"
        row.reviewed_by = admin.id
        row.reviewed_at = datetime.utcnow()
    _audit(db, admin, "REVIEW_AI_FEEDBACK_ANALYSIS", "ai_feedback_analysis", row.id, None, {"reviewed": payload.reviewed})
    db.commit()
    db.refresh(row)
    return _ai_out(row)


@router.get("/evaluation-cycles/{cycle_id}/employees/{employee_id}/preliminary-report", response_model=PreliminaryReportOut)
def preliminary_report(cycle_id: int, employee_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    _cycle(db, cycle_id)
    employee = _employee(db, employee_id)
    score = db.query(EvaluationScore).filter(EvaluationScore.cycle_id == cycle_id, EvaluationScore.employee_id == employee_id).first()
    alerts = db.query(EvaluationAlert).filter(EvaluationAlert.cycle_id == cycle_id, EvaluationAlert.employee_id == employee_id).all()
    reviews = db.query(Review360).filter(Review360.cycle_id == cycle_id, Review360.evaluated_id == employee_id).order_by(Review360.id.desc()).all()
    ai = db.query(AiFeedbackAnalysis).filter(AiFeedbackAnalysis.cycle_id == cycle_id, AiFeedbackAnalysis.employee_id == employee_id).first()
    return PreliminaryReportOut(
        employee=_employee_out(employee),
        score=_score_out(score, alerts) if score else None,
        reviews=[_review_out(row) for row in reviews],
        ai_analysis=_ai_out(ai) if ai else None,
        alerts=[_alert_out(row) for row in alerts],
    )


@router.get("/evaluation-cycles/{cycle_id}/calibration", response_model=list[EvaluationScoreOut])
def get_calibration(cycle_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return list_scores(cycle_id, db, _admin)


@router.patch("/evaluation-cycles/{cycle_id}/employees/{employee_id}/calibration", response_model=EvaluationScoreOut)
def calibrate_employee(cycle_id: int, employee_id: int, payload: CalibrationPayload, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    score = db.query(EvaluationScore).filter(EvaluationScore.cycle_id == cycle_id, EvaluationScore.employee_id == employee_id).first()
    if not score:
        raise HTTPException(status_code=404, detail="Score nao encontrado")
    try:
        EvaluationScoringService(db, actor_id=admin.id).calibrate(cycle, score, payload.final_category, payload.calibration_justification)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(score)
    alerts = db.query(EvaluationAlert).filter(EvaluationAlert.cycle_id == cycle_id, EvaluationAlert.employee_id == employee_id, EvaluationAlert.resolved_at.is_(None)).all()
    return _score_out(score, alerts)


@router.get("/evaluation-cycles/{cycle_id}/final-list", response_model=list[FinalListRowOut])
def final_list(
    cycle_id: int,
    department: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    rows = list_scores(cycle_id, db, _admin)
    if department:
        rows = [row for row in rows if row.department == department]
    if category:
        rows = [row for row in rows if row.final_category == category]
    rows = sorted(rows, key=lambda row: (row.preliminary_final_score or row.behavior_score or -1), reverse=True)
    final_rows: list[FinalListRowOut] = []
    for index, row in enumerate(rows, start=1):
        payload = row.model_dump()
        payload["position"] = index
        final_rows.append(FinalListRowOut(**payload))
    return final_rows


@router.get("/evaluation-cycles/{cycle_id}/final-list/export")
def export_final_list(cycle_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    rows = final_list(cycle_id, None, None, db, admin)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "position",
        "employee",
        "department",
        "position_name",
        "manager",
        "behavior_360_score",
        "performance_rpm_ihpe_score",
        "manager_score",
        "final_score",
        "suggested_category",
        "final_category",
        "justification",
    ])
    for row in rows:
        writer.writerow([
            row.position,
            row.employee_name,
            row.department or "",
            row.position or "",
            row.manager_name or "",
            row.behavior_score or "",
            row.performance_score or "",
            row.potential_score or "",
            row.preliminary_final_score or "",
            row.suggested_category or "",
            row.final_category or "",
            row.calibration_justification or "",
        ])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=evaluation_final_list_{cycle_id}.csv"},
    )


@router.get("/evaluation-cycles/{cycle_id}/final-report/html", response_class=HTMLResponse)
def final_report_html(cycle_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    cycle = _cycle(db, cycle_id)
    rows = final_list(cycle_id, None, None, db, admin)
    rh_by_employee = {
        row.employee_id: row
        for row in db.query(EmployeeRhData).filter(EmployeeRhData.cycle_id == cycle_id).all()
    }
    ai_by_employee = {
        row.employee_id: row
        for row in db.query(AiFeedbackAnalysis).filter(AiFeedbackAnalysis.cycle_id == cycle_id).all()
    }
    generated_at = datetime.utcnow().strftime("%d/%m/%Y %H:%M")

    def fmt(value):
        return "-" if value is None else f"{value:.2f}"

    def esc(value):
        text = "" if value is None else str(value)
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    body = [
        "<!doctype html><html><head><meta charset='utf-8'><title>Relatório Final de Avaliação</title>",
        "<style>body{font-family:Arial,sans-serif;color:#172033;margin:32px}h1{font-size:28px}h2{margin-top:28px;border-bottom:1px solid #d8dee9;padding-bottom:6px}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #d8dee9;padding:8px;text-align:left;font-size:13px}th{background:#eef3fb}.card{border:1px solid #d8dee9;border-radius:10px;padding:14px;margin:16px 0}.muted{color:#64748b}.badge{display:inline-block;padding:3px 8px;border-radius:999px;background:#eef3fb;font-weight:bold}</style>",
        "</head><body>",
        f"<h1>Relatório Final de Avaliação - {esc(cycle.name)}</h1>",
        f"<p class='muted'>Gerado em {generated_at}. Documento de apoio à decisão gerencial.</p>",
        "<h2>1. Metodologia e contexto</h2>",
        "<p>O processo consolida avaliação 360, indicadores RPM/IHPE, nota do gestor e dados de RH. A autoavaliação é desconsiderada. A fórmula do score final usa 360 com peso 45%, nota do gestor com peso 45% e RPM/IHPE com peso 10%. RPM deve representar horas em projetos sobre horas totais, excluindo atividades genéricas e treinamento. IHPE deve ser recalculado por mês como horas em entregáveis sobre horas trabalhadas e depois convertido na média dos meses apurados.</p>",
        "<p>A IA, quando usada, resume comentários, identifica padrões e sugere feedback textual. Ela não define nota, categoria ou promoção. A decisão final permanece humana, calibrada e auditável.</p>",
        "<h2>2. Sumário executivo</h2>",
        "<table><thead><tr><th>Pos.</th><th>Colaborador</th><th>ANC</th><th>Elegibilidade</th><th>360</th><th>RPM/IHPE</th><th>Gestor</th><th>Score final</th><th>Categoria</th></tr></thead><tbody>",
    ]
    for row in rows:
        rh = rh_by_employee.get(row.employee_id)
        eligibility = rh.eligibility_reason if rh else "RH não importado"
        body.append(
            f"<tr><td>{row.position}</td><td>{esc(row.employee_name)}</td><td>{esc(rh.career_level if rh else '-')}</td>"
            f"<td>{esc(eligibility)}</td><td>{fmt(row.behavior_score)}</td><td>{fmt(row.performance_score)}</td>"
            f"<td>{fmt(row.potential_score)}</td><td>{fmt(row.preliminary_final_score)}</td><td>{esc(row.final_category or row.suggested_category or '-')}</td></tr>"
        )
    body.append("</tbody></table>")
    body.append("<h2>3. Relatórios individuais</h2>")
    for row in rows:
        rh = rh_by_employee.get(row.employee_id)
        ai = ai_by_employee.get(row.employee_id)
        body.append("<div class='card'>")
        body.append(f"<h3>{esc(row.employee_name)}</h3>")
        body.append(
            f"<p><span class='badge'>ANC {esc(rh.career_level if rh else '-')}</span> "
            f"<span class='badge'>360 {fmt(row.behavior_score)}</span> "
            f"<span class='badge'>RPM/IHPE {fmt(row.performance_score)}</span> "
            f"<span class='badge'>Score {fmt(row.preliminary_final_score)}</span></p>"
        )
        body.append(f"<p><strong>Elegibilidade:</strong> {esc(rh.eligibility_reason if rh else 'Dados de RH não importados.')}</p>")
        if ai:
            body.append(f"<p><strong>Resumo IA:</strong> {esc(ai.summary)}</p>")
            if ai.strengths_json:
                body.append("<p><strong>Pontos fortes:</strong> " + esc("; ".join(ai.strengths_json)) + "</p>")
            if ai.attention_points_json:
                body.append("<p><strong>Áreas para melhorar:</strong> " + esc("; ".join(ai.attention_points_json)) + "</p>")
            body.append(f"<p><strong>Feedback compilado:</strong> {esc(ai.suggested_feedback)}</p>")
        else:
            body.append("<p><strong>Feedback compilado:</strong> Rode a análise IA do ciclo para preencher esta seção.</p>")
        body.append("</div>")
    body.append("</body></html>")
    return HTMLResponse("".join(body))


@router.get("/evaluation-cycles/{cycle_id}/alerts", response_model=list[EvaluationAlertOut])
def list_alerts(cycle_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    _cycle(db, cycle_id)
    return [_alert_out(row) for row in db.query(EvaluationAlert).filter(EvaluationAlert.cycle_id == cycle_id).order_by(EvaluationAlert.created_at.desc()).all()]


@router.get("/evaluation-cycles/{cycle_id}/employees/{employee_id}/alerts", response_model=list[EvaluationAlertOut])
def employee_alerts(cycle_id: int, employee_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    _cycle(db, cycle_id)
    _employee(db, employee_id)
    return [_alert_out(row) for row in db.query(EvaluationAlert).filter(EvaluationAlert.cycle_id == cycle_id, EvaluationAlert.employee_id == employee_id).all()]


@router.patch("/alerts/{alert_id}/resolve", response_model=EvaluationAlertOut)
def resolve_alert(alert_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    alert = db.query(EvaluationAlert).filter(EvaluationAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta nao encontrado")
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = admin.id
    _audit(db, admin, "RESOLVE_ALERT", "evaluation_alerts", alert.id, None, {"resolved": True})
    db.commit()
    db.refresh(alert)
    return _alert_out(alert)


@router.get("/evaluation-cycles/{cycle_id}/dashboard", response_model=DashboardOut)
def dashboard(cycle_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    scores = list_scores(cycle_id, db, admin)
    alerts = list_alerts(cycle_id, db, admin)
    final_scores = [score.preliminary_final_score for score in scores if score.preliminary_final_score is not None]
    suggested: dict[str, int] = {}
    final: dict[str, int] = {}
    departments: dict[str, int] = {}
    for score in scores:
        if score.suggested_category:
            suggested[score.suggested_category] = suggested.get(score.suggested_category, 0) + 1
        if score.final_category:
            final[score.final_category] = final.get(score.final_category, 0) + 1
        key = score.department or "Sem area"
        departments[key] = departments.get(key, 0) + 1
    return DashboardOut(
        cycle_id=cycle_id,
        total_evaluated=len(scores),
        average_final_score=round(sum(final_scores) / len(final_scores), 2) if final_scores else None,
        suggested_by_category=suggested,
        final_by_category=final,
        by_department=departments,
        alerts=alerts,
    )

