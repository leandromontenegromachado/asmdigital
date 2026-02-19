from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Pagination(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class Message(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
    details: Optional[Any] = None
