from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Time, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class FalaAiCheckin(Base):
    __tablename__ = "fala_ai_checkins"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tipo = Column(String(40), nullable=False, default="manual")
    origem = Column(String(40), nullable=False, default="web")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class FalaAiReminder(Base):
    __tablename__ = "fala_ai_reminders"

    id = Column(Integer, primary_key=True, index=True)
    mensagem = Column(Text, nullable=False)
    horario = Column(Time(timezone=False), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class FalaAiLog(Base):
    __tablename__ = "fala_ai_logs"

    id = Column(Integer, primary_key=True, index=True)
    evento = Column(String(120), nullable=False, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
