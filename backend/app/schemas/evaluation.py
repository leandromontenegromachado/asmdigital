from datetime import date, datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


CycleStatus = Literal["RASCUNHO", "EM_COLETA", "EM_ANALISE", "EM_CALIBRACAO", "FINALIZADO"]
RelationType = Literal["MANAGER", "PEER", "INTERNAL_CLIENT", "SELF"]
EvaluationCategory = Literal["DESTAQUE", "MUITO_BOM", "BOM", "EM_DESENVOLVIMENTO", "ATENCAO"]
AlertType = Literal[
    "HIGH_PERFORMANCE_LOW_BEHAVIOR",
    "LOW_PERFORMANCE_HIGH_BEHAVIOR",
    "MANAGER_PEER_DIVERGENCE",
    "MISSING_DATA",
]
AlertSeverity = Literal["LOW", "MEDIUM", "HIGH"]
ImportStatus = Literal["UPLOADED", "MAPPED", "VALIDATED", "IMPORTED", "ERROR"]
ImportRowStatus = Literal["PENDING", "VALID", "IMPORTED", "ERROR"]
AiAnalysisStatus = Literal["PENDING", "PROCESSED", "REVIEWED", "ERROR"]


class EvaluationCycleBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    start_date: date
    end_date: date
    status: CycleStatus = "RASCUNHO"
    performance_weight: float = Field(default=0.10, ge=0, le=1)
    behavior_weight: float = Field(default=0.45, ge=0, le=1)
    potential_weight: float = Field(default=0.45, ge=0, le=1)
    notes: str | None = None


class EvaluationCycleCreate(EvaluationCycleBase):
    pass


class EvaluationCycleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    performance_weight: float | None = Field(default=None, ge=0, le=1)
    behavior_weight: float | None = Field(default=None, ge=0, le=1)
    potential_weight: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = None


class EvaluationCycleStatusUpdate(BaseModel):
    status: CycleStatus


class EvaluationCycleOut(EvaluationCycleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmployeeBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    teams_user_id: str | None = None
    matricula: str | None = None
    cargo: str | None = None
    setor: str | None = None
    department: str | None = None
    position: str | None = None
    manager_id: int | None = None
    active: bool = True
    recebe_notificacao: bool = True
    participa_avaliacao: bool = True
    canal_preferencial: str = "email"


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    email: EmailStr | None = None
    teams_user_id: str | None = None
    matricula: str | None = None
    cargo: str | None = None
    setor: str | None = None
    department: str | None = None
    position: str | None = None
    manager_id: int | None = None
    active: bool | None = None
    recebe_notificacao: bool | None = None
    participa_avaliacao: bool | None = None
    canal_preferencial: str | None = None


class EmployeeOut(EmployeeBase):
    id: int
    manager_name: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IndicatorPayload(BaseModel):
    rpm_original: float | None = Field(default=None, ge=0)
    ihpe_original: float | None = Field(default=None, ge=0)


class IndicatorOut(BaseModel):
    id: int
    cycle_id: int
    employee_id: int
    employee_name: str | None = None
    rpm_original: float | None
    rpm_normalized: float | None
    ihpe_original: float | None
    ihpe_normalized: float | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OperationalImportOut(BaseModel):
    imported_rows: int
    updated_employees: int
    updated_indicators: int = 0
    updated_rh_records: int = 0
    warnings: list[str] = []


class EmployeeRhDataOut(BaseModel):
    id: int
    cycle_id: int
    employee_id: int
    employee_name: str | None = None
    career_level: int | None
    last_merit_date: date | None
    admission_date: date | None
    is_level_one_separate_budget: bool
    eligible_for_merit: bool
    eligibility_reason: str | None

    class Config:
        from_attributes = True


class Review360Create(BaseModel):
    evaluator_id: int | None = None
    evaluated_id: int
    evaluator_email: EmailStr | None = None
    evaluator_name: str | None = None
    evaluated_email: EmailStr | None = None
    evaluated_name: str | None = None
    relation_type: RelationType
    score: float | None = Field(default=None, ge=0, le=100)
    general_score: float | None = Field(default=None, ge=0, le=100)
    communication_score: float | None = Field(default=None, ge=0, le=100)
    teamwork_score: float | None = Field(default=None, ge=0, le=100)
    commitment_score: float | None = Field(default=None, ge=0, le=100)
    autonomy_score: float | None = Field(default=None, ge=0, le=100)
    quality_score: float | None = Field(default=None, ge=0, le=100)
    problem_solving_score: float | None = Field(default=None, ge=0, le=100)
    strengths_comment: str | None = None
    improvement_comment: str | None = None
    general_comment: str | None = None
    comment: str | None = None


class Review360Out(Review360Create):
    id: int
    cycle_id: int
    import_id: int | None = None
    import_row_id: int | None = None
    evaluator_name: str | None = None
    evaluated_name: str | None = None
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PotentialPayload(BaseModel):
    score: float = Field(ge=0, le=100)
    comment: str | None = None


class PotentialOut(BaseModel):
    id: int
    cycle_id: int
    employee_id: int
    employee_name: str | None = None
    score: float
    comment: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvaluationAlertOut(BaseModel):
    id: int
    cycle_id: int
    employee_id: int
    employee_name: str | None = None
    alert_type: AlertType
    message: str
    severity: AlertSeverity
    created_at: datetime
    resolved_at: datetime | None
    resolved_by: int | None

    class Config:
        from_attributes = True


class EvaluationScoreOut(BaseModel):
    id: int
    cycle_id: int
    employee_id: int
    employee_name: str
    department: str | None
    position: str | None
    manager_name: str | None = None
    performance_score: float | None
    behavior_score: float | None
    potential_score: float | None
    preliminary_final_score: float | None
    suggested_category: EvaluationCategory | None
    final_category: EvaluationCategory | None
    nine_box_position: str | None
    calibration_justification: str | None
    calibrated_by: int | None
    calibrated_at: datetime | None
    alerts: list[EvaluationAlertOut] = []

    class Config:
        from_attributes = True


class CalculateScoresOut(BaseModel):
    cycle_id: int
    processed: int
    incomplete: int
    alerts_generated: int


class CalibrationPayload(BaseModel):
    final_category: EvaluationCategory
    calibration_justification: str | None = None


class FinalListRowOut(EvaluationScoreOut):
    position: int


class EvaluationImportOut(BaseModel):
    id: int
    cycle_id: int
    file_name: str
    status: ImportStatus
    uploaded_by: int | None
    uploaded_at: datetime
    column_mapping_json: dict[str, str] | None
    total_rows: int
    valid_rows: int
    invalid_rows: int
    error_message: str | None
    headers: list[str] = []

    class Config:
        from_attributes = True


class ImportColumnMappingPayload(BaseModel):
    mapping: dict[str, str]


class EvaluationImportRowOut(BaseModel):
    id: int
    import_id: int
    row_number: int
    raw_data_json: dict[str, Any]
    normalized_data_json: dict[str, Any] | None
    status: ImportRowStatus
    error_message: str | None

    class Config:
        from_attributes = True


class ImportValidationOut(BaseModel):
    import_id: int
    status: ImportStatus
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: list[EvaluationImportRowOut]


class ImportConfirmOut(BaseModel):
    import_id: int
    imported_rows: int
    created_reviews: int


class QualitativeAlertOut(BaseModel):
    type: str
    description: str
    severity: AlertSeverity


class AiFeedbackAnalysisOut(BaseModel):
    id: int
    cycle_id: int
    employee_id: int
    employee_name: str | None = None
    status: AiAnalysisStatus
    summary: str | None
    strengths_json: list[str] | None
    attention_points_json: list[str] | None
    recurring_themes_json: list[str] | None
    qualitative_alerts_json: list[dict[str, Any]] | None
    suggested_feedback: str | None
    model_used: str | None
    raw_response_json: dict[str, Any] | None
    error_message: str | None
    reviewed_by: int | None
    reviewed_at: datetime | None

    class Config:
        from_attributes = True


class AiAnalysisReviewPayload(BaseModel):
    reviewed: bool = True


class PreliminaryReportOut(BaseModel):
    employee: EmployeeOut
    score: EvaluationScoreOut | None
    reviews: list[Review360Out]
    ai_analysis: AiFeedbackAnalysisOut | None
    alerts: list[EvaluationAlertOut]


class DashboardOut(BaseModel):
    cycle_id: int
    total_evaluated: int
    average_final_score: float | None
    suggested_by_category: dict[str, int]
    final_by_category: dict[str, int]
    by_department: dict[str, int]
    alerts: list[EvaluationAlertOut]
