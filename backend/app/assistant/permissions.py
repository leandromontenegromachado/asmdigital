from __future__ import annotations

from app.models import User


ACTION_ROLES = {
    "LIST_LATE_PROJECTS": {"admin", "gerente", "funcionario", "viewer"},
    "NOTIFY_RESPONSIBLES": {"admin", "gerente"},
    "CREATE_MEETING": {"admin", "gerente", "funcionario", "viewer"},
    "HELP": {"admin", "gerente", "funcionario", "viewer"},
}


def can_execute(user: User | None, action: str) -> bool:
    if user is None:
        return action in {"HELP"}
    role = (user.role or "funcionario").strip().lower()
    if role == "viewer":
        role = "funcionario"
    return role in ACTION_ROLES.get(action, {"admin"})
