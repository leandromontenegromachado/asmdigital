from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class MappingOut(BaseModel):
    id: int
    connector_id: int | None
    mapping_type: str
    rules_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MappingUpdate(BaseModel):
    connector_id: int | None = None
    rules_json: dict[str, Any]


class MappingPreviewField(BaseModel):
    raw: Optional[str] = None
    processed: Optional[str] = None
    source: Optional[str] = None
    is_warning: bool = False


class MappingPreviewTicket(BaseModel):
    id: str
    title: str
    cliente: MappingPreviewField
    sistema: MappingPreviewField
    entrega: MappingPreviewField
    source_ref: Optional[str] = None
    source_url: Optional[str] = None


class MappingPreviewResponse(BaseModel):
    tickets: list[MappingPreviewTicket]
