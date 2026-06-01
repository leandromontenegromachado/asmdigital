from __future__ import annotations

from app.models import User


READ_ACTIONS = {"list", "status", "capabilities", "list_late_projects", "analyze"}
ADMIN_ACTIONS = {
    ("employees", "create"),
    ("employees", "update"),
    ("employees", "delete"),
    ("connectors", "update"),
    ("ai_models", "update"),
}
MANAGER_ACTIONS = {
    ("reports_ai", "run_report"),
    ("reports_redmine", "run_report"),
    ("notifications", "send"),
    ("routines", "create"),
    ("routines", "update"),
    ("routines", "delete"),
    ("routines", "run"),
    ("pending_items", "create"),
    ("pending_items", "resolve"),
    ("pending_items", "ignore"),
    ("pending_items", "escalate"),
}


def can_execute(user: User | None, domain: str, action: str | None = None) -> bool:
    action_name = (action or domain or "").strip().lower()
    domain_name = (domain or "general").strip().lower()
    if user is None:
        return domain_name == "general" and action_name in {"capabilities", "help"}

    role = (user.role or "funcionario").strip().lower()
    if role == "viewer":
        role = "funcionario"
    if role == "admin":
        return True
    if action_name in READ_ACTIONS or action_name.startswith("list"):
        return True
    if domain_name == "meetings" and action_name == "create":
        return role in {"gerente", "funcionario"}
    if (domain_name, action_name) in ADMIN_ACTIONS:
        return False
    if (domain_name, action_name) in MANAGER_ACTIONS:
        return role == "gerente"
    return role == "gerente"

