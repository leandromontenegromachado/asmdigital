from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.assistant.schemas import AssistantPlan
from app.models import User


@dataclass(frozen=True)
class ActionResult:
    message: str
    data: dict[str, Any]
    success: bool = True
    errors: list[str] | None = None


class AssistantActionHandler(Protocol):
    domain: str

    def preview(self, db: Session, plan: AssistantPlan, user: User | None) -> dict[str, Any]:
        ...

    def execute(self, db: Session, plan: AssistantPlan, user: User | None) -> ActionResult:
        ...


def compact_items(items: list[dict[str, Any]], limit: int = 10) -> dict[str, Any]:
    return {"total": len(items), "items": items[:limit]}
