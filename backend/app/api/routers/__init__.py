from app.api.routers.auth import router as auth
from app.api.routers.connectors import router as connectors
from app.api.routers.mappings import router as mappings
from app.api.routers.reports import router as reports
from app.api.routers.prompt_reports import router as prompt_reports
from app.api.routers.automations import router as automations
from app.api.routers.users import router as users

__all__ = ["auth", "connectors", "mappings", "reports", "prompt_reports", "automations", "users"]
