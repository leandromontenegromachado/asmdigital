from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.modules.fala_ai.models import FalaAiCheckin, FalaAiLog, FalaAiReminder


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="admin", nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Connector(Base):
    __tablename__ = "connectors"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    config_json = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    mappings = relationship("Mapping", back_populates="connector")


class Mapping(Base):
    __tablename__ = "mappings"

    id = Column(Integer, primary_key=True, index=True)
    connector_id = Column(Integer, ForeignKey("connectors.id"), nullable=True)
    mapping_type = Column(String(80), nullable=False, index=True)
    rules_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    connector = relationship("Connector", back_populates="mappings")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(80), nullable=False, index=True)
    params_json = Column(JSONB, nullable=False, default=dict)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String(40), nullable=False, default="completed")
    file_path = Column(String(500), nullable=True)

    rows = relationship("ReportRow", back_populates="report", cascade="all, delete-orphan")


class ReportRow(Base):
    __tablename__ = "report_rows"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False, index=True)
    cliente = Column(String(200), nullable=True)
    sistema = Column(String(200), nullable=True)
    entrega = Column(String(200), nullable=True)
    source_ref = Column(String(120), nullable=True)
    source_url = Column(String(500), nullable=True)
    raw_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    report = relationship("Report", back_populates="rows")


class PromptReportTemplate(Base):
    __tablename__ = "prompt_report_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    connector_id = Column(Integer, ForeignKey("connectors.id"), nullable=False, index=True)
    prompt_text = Column(Text, nullable=False)
    params_json = Column(JSONB, nullable=False, default=dict)
    schedule_cron = Column(String(120), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    connector = relationship("Connector")


class Automation(Base):
    __tablename__ = "automations"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(120), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    schedule_cron = Column(String(120), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    params_json = Column(JSONB, nullable=False, default=dict)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)

    runs = relationship("AutomationRun", back_populates="automation")
    notification_rules = relationship("NotificationRule", back_populates="automation", cascade="all, delete-orphan")


class AutomationRun(Base):
    __tablename__ = "automation_runs"

    id = Column(Integer, primary_key=True, index=True)
    automation_id = Column(Integer, ForeignKey("automations.id"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(40), nullable=False, default="running")
    summary_json = Column(JSONB, nullable=False, default=dict)
    error_text = Column(Text, nullable=True)

    automation = relationship("Automation", back_populates="runs")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("automation_runs.id"), nullable=True, index=True)
    automation_id = Column(Integer, ForeignKey("automations.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    channel = Column(String(80), nullable=False)
    recipient = Column(String(200), nullable=True)
    to_ref = Column(String(200), nullable=True)
    subject = Column(String(200), nullable=True)
    message = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
    status = Column(String(40), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    data_envio = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    simulation = Column(Boolean, nullable=False, default=False)

    execution = relationship("AutomationRun")
    automation = relationship("Automation")
    employee = relationship("Employee")


class ManagementEvent(Base):
    __tablename__ = "management_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(80), nullable=False, index=True)
    source_type = Column(String(80), nullable=True, index=True)
    source_id = Column(String(120), nullable=True, index=True)
    status = Column(String(40), nullable=False, default="pending", index=True)
    severity = Column(String(40), nullable=False, default="medium", index=True)
    responsible_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    payload_json = Column(JSONB, nullable=False, default=dict)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    ignored_at = Column(DateTime(timezone=True), nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    responsible = relationship("Employee")
    creator = relationship("User")


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    channel = Column(String(40), nullable=False, default="email")
    subject = Column(String(200), nullable=True)
    body = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NotificationRule(Base):
    __tablename__ = "notification_rules"

    id = Column(Integer, primary_key=True, index=True)
    automation_id = Column(Integer, ForeignKey("automations.id"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    send_condition = Column(String(120), nullable=True)
    recipient_type = Column(String(60), nullable=False, default="responsavel")
    preferred_channel = Column(String(40), nullable=False, default="email")
    fallback_channel = Column(String(40), nullable=True)
    template_id = Column(Integer, ForeignKey("notification_templates.id"), nullable=True)
    requires_approval = Column(Boolean, nullable=False, default=False)
    notify_manager = Column(Boolean, nullable=False, default=False)
    manager_condition = Column(String(120), nullable=True)
    params_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    automation = relationship("Automation", back_populates="notification_rules")
    template = relationship("NotificationTemplate")


class EvaluationCycle(Base):
    __tablename__ = "evaluation_cycles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(30), nullable=False, default="RASCUNHO")
    performance_weight = Column(Float, nullable=False, default=0.10)
    behavior_weight = Column(Float, nullable=False, default=0.45)
    potential_weight = Column(Float, nullable=False, default=0.45)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    indicators = relationship("PerformanceIndicator", back_populates="cycle", cascade="all, delete-orphan")
    imports = relationship("EvaluationImport", back_populates="cycle", cascade="all, delete-orphan")
    reviews = relationship("Review360", back_populates="cycle", cascade="all, delete-orphan")
    potentials = relationship("PotentialScore", back_populates="cycle", cascade="all, delete-orphan")
    scores = relationship("EvaluationScore", back_populates="cycle", cascade="all, delete-orphan")
    alerts = relationship("EvaluationAlert", back_populates="cycle", cascade="all, delete-orphan")
    ai_feedback = relationship("AiFeedbackAnalysis", back_populates="cycle", cascade="all, delete-orphan")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=False, unique=True, index=True)
    teams_user_id = Column(String(200), nullable=True)
    matricula = Column(String(80), nullable=True, unique=True, index=True)
    cargo = Column(String(120), nullable=True)
    setor = Column(String(120), nullable=True, index=True)
    department = Column(String(120), nullable=True, index=True)
    position = Column(String(120), nullable=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    recebe_notificacao = Column(Boolean, nullable=False, default=True)
    participa_avaliacao = Column(Boolean, nullable=False, default=True)
    canal_preferencial = Column(String(40), nullable=False, default="email")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    manager = relationship("Employee", remote_side=[id])
    rh_data = relationship("EmployeeRhData", back_populates="employee", cascade="all, delete-orphan")


class EmployeeRhData(Base):
    __tablename__ = "employee_rh_data"
    __table_args__ = (UniqueConstraint("cycle_id", "employee_id", name="uq_employee_rh_data_cycle_employee"),)

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("evaluation_cycles.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    career_level = Column(Integer, nullable=True)
    last_merit_date = Column(Date, nullable=True)
    admission_date = Column(Date, nullable=True)
    is_level_one_separate_budget = Column(Boolean, nullable=False, default=False)
    eligible_for_merit = Column(Boolean, nullable=False, default=True)
    eligibility_reason = Column(Text, nullable=True)
    raw_data_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    cycle = relationship("EvaluationCycle")
    employee = relationship("Employee", back_populates="rh_data")


class PerformanceIndicator(Base):
    __tablename__ = "performance_indicators"
    __table_args__ = (UniqueConstraint("cycle_id", "employee_id", name="uq_performance_indicator_cycle_employee"),)

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("evaluation_cycles.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    rpm_original = Column(Float, nullable=True)
    rpm_normalized = Column(Float, nullable=True)
    ihpe_original = Column(Float, nullable=True)
    ihpe_normalized = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    cycle = relationship("EvaluationCycle", back_populates="indicators")
    employee = relationship("Employee")


class EvaluationImport(Base):
    __tablename__ = "evaluation_imports"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("evaluation_cycles.id"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    status = Column(String(30), nullable=False, default="UPLOADED", index=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    column_mapping_json = Column(JSONB, nullable=True)
    total_rows = Column(Integer, nullable=False, default=0)
    valid_rows = Column(Integer, nullable=False, default=0)
    invalid_rows = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)

    cycle = relationship("EvaluationCycle", back_populates="imports")
    rows = relationship("EvaluationImportRow", back_populates="import_record", cascade="all, delete-orphan")


class EvaluationImportRow(Base):
    __tablename__ = "evaluation_import_rows"

    id = Column(Integer, primary_key=True, index=True)
    import_id = Column(Integer, ForeignKey("evaluation_imports.id"), nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    raw_data_json = Column(JSONB, nullable=False)
    normalized_data_json = Column(JSONB, nullable=True)
    status = Column(String(30), nullable=False, default="PENDING", index=True)
    error_message = Column(Text, nullable=True)

    import_record = relationship("EvaluationImport", back_populates="rows")
    reviews = relationship("Review360", back_populates="import_row")


class Review360(Base):
    __tablename__ = "reviews_360"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("evaluation_cycles.id"), nullable=False, index=True)
    import_id = Column(Integer, ForeignKey("evaluation_imports.id"), nullable=True, index=True)
    import_row_id = Column(Integer, ForeignKey("evaluation_import_rows.id"), nullable=True, index=True)
    evaluator_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    evaluator_email = Column(String(200), nullable=True)
    evaluator_name = Column(String(200), nullable=True)
    evaluated_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    evaluated_email = Column(String(200), nullable=True)
    evaluated_name = Column(String(200), nullable=True)
    relation_type = Column(String(30), nullable=False, index=True)
    score = Column(Float, nullable=True)
    general_score = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    teamwork_score = Column(Float, nullable=True)
    commitment_score = Column(Float, nullable=True)
    autonomy_score = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)
    problem_solving_score = Column(Float, nullable=True)
    strengths_comment = Column(Text, nullable=True)
    improvement_comment = Column(Text, nullable=True)
    general_comment = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    cycle = relationship("EvaluationCycle", back_populates="reviews")
    import_record = relationship("EvaluationImport")
    import_row = relationship("EvaluationImportRow", back_populates="reviews")
    evaluator = relationship("Employee", foreign_keys=[evaluator_id])
    evaluated = relationship("Employee", foreign_keys=[evaluated_id])


class PotentialScore(Base):
    __tablename__ = "potential_scores"
    __table_args__ = (UniqueConstraint("cycle_id", "employee_id", name="uq_potential_score_cycle_employee"),)

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("evaluation_cycles.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    score = Column(Float, nullable=False)
    comment = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    cycle = relationship("EvaluationCycle", back_populates="potentials")
    employee = relationship("Employee")


class EvaluationScore(Base):
    __tablename__ = "evaluation_scores"
    __table_args__ = (UniqueConstraint("cycle_id", "employee_id", name="uq_evaluation_score_cycle_employee"),)

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("evaluation_cycles.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    performance_score = Column(Float, nullable=True)
    behavior_score = Column(Float, nullable=True)
    potential_score = Column(Float, nullable=True)
    preliminary_final_score = Column(Float, nullable=True)
    suggested_category = Column(String(40), nullable=True)
    final_category = Column(String(40), nullable=True)
    nine_box_position = Column(String(40), nullable=True)
    calibration_justification = Column(Text, nullable=True)
    calibrated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    calibrated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    cycle = relationship("EvaluationCycle", back_populates="scores")
    employee = relationship("Employee")


class EvaluationAlert(Base):
    __tablename__ = "evaluation_alerts"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("evaluation_cycles.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    alert_type = Column(String(60), nullable=False, index=True)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    cycle = relationship("EvaluationCycle", back_populates="alerts")
    employee = relationship("Employee")


class AiFeedbackAnalysis(Base):
    __tablename__ = "ai_feedback_analysis"
    __table_args__ = (UniqueConstraint("cycle_id", "employee_id", name="uq_ai_feedback_analysis_cycle_employee"),)

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("evaluation_cycles.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="PENDING", index=True)
    summary = Column(Text, nullable=True)
    strengths_json = Column(JSONB, nullable=True)
    attention_points_json = Column(JSONB, nullable=True)
    recurring_themes_json = Column(JSONB, nullable=True)
    qualitative_alerts_json = Column(JSONB, nullable=True)
    suggested_feedback = Column(Text, nullable=True)
    model_used = Column(String(120), nullable=True)
    raw_response_json = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    cycle = relationship("EvaluationCycle", back_populates="ai_feedback")
    employee = relationship("Employee")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "User",
    "Connector",
    "Mapping",
    "Report",
    "ReportRow",
    "PromptReportTemplate",
    "Automation",
    "AutomationRun",
    "Notification",
    "NotificationRule",
    "NotificationTemplate",
    "EvaluationCycle",
    "Employee",
    "EmployeeRhData",
    "EvaluationImport",
    "EvaluationImportRow",
    "PerformanceIndicator",
    "Review360",
    "PotentialScore",
    "EvaluationScore",
    "EvaluationAlert",
    "AiFeedbackAnalysis",
    "AuditLog",
    "FalaAiCheckin",
    "FalaAiReminder",
    "FalaAiLog",
]
