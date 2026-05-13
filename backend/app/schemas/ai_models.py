from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AiModelBase(BaseModel):
    name: str
    provider: str = "google_gemini"
    model_id: str
    description: Optional[str] = None
    api_key_env: Optional[str] = "FALA_AI_GEMINI_API_KEY"
    is_active: bool = True
    is_default: bool = False


class AiModelCreate(AiModelBase):
    pass


class AiModelUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model_id: Optional[str] = None
    description: Optional[str] = None
    api_key_env: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class AiModelOut(AiModelBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AiModelAssignmentUpdate(BaseModel):
    model_id: int


class AiModelAssignmentOut(BaseModel):
    id: int
    feature_key: str
    feature_label: str
    model_id: int
    model_name: str
    provider: str
    provider_label: str
    provider_supported: bool
    external_model_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
