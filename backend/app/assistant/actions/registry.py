from __future__ import annotations

from app.assistant.actions.capabilities import CapabilitiesAction
from app.assistant.actions.employees import EmployeesAction
from app.assistant.actions.pending_items import PendingItemsAction
from app.assistant.actions.reports import ReportsAction
from app.assistant.actions.routines import RoutinesAction
from app.assistant.actions.notifications import NotificationsAction


_CAPABILITIES = CapabilitiesAction()
_REPORTS = ReportsAction()

ACTION_REGISTRY = {
    "general": _CAPABILITIES,
    "reports_ai": _REPORTS,
    "reports_redmine": _REPORTS,
    "routines": RoutinesAction(),
    "notifications": NotificationsAction(),
    "employees": EmployeesAction(),
    "pending_items": PendingItemsAction(),
}


def get_action_handler(domain: str):
    return ACTION_REGISTRY.get((domain or "general").strip().lower())
