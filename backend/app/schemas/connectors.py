from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ConnectorBase(BaseModel):
    type: str
    name: str
    config_json: dict[str, Any]
    is_active: bool = True


class ConnectorCreate(ConnectorBase):
    pass


class ConnectorUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    config_json: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class ConnectorOut(ConnectorBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConnectorTestResult(BaseModel):
    ok: bool
    message: str
    details: dict[str, Any] | None = None


class RedmineQueryOut(BaseModel):
    id: int
    name: str
    is_public: bool | None = None
