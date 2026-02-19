from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


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
    channel = Column(String(80), nullable=False)
    to_ref = Column(String(200), nullable=True)
    subject = Column(String(200), nullable=True)
    body = Column(Text, nullable=True)
    status = Column(String(40), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    simulation = Column(Boolean, nullable=False, default=False)
