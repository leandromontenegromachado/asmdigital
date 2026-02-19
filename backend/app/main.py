from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.wait_for_db import wait_for_db
from app.api.routers.auth import router as auth_router
from app.api.routers.connectors import router as connectors_router
from app.api.routers.mappings import router as mappings_router
from app.api.routers.reports import router as reports_router
from app.api.routers.automations import router as automations_router
from app.api.routers.users import router as users_router
from app.api.routers.prompt_reports import router as prompt_reports_router
from app.scheduler import start_scheduler, shutdown_scheduler

configure_logging()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"] ,
)


@app.on_event("startup")
def on_startup() -> None:
    wait_for_db()
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    shutdown_scheduler()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(connectors_router, prefix=settings.api_prefix)
app.include_router(mappings_router, prefix=settings.api_prefix)
app.include_router(reports_router, prefix=settings.api_prefix)
app.include_router(prompt_reports_router, prefix=settings.api_prefix)
app.include_router(automations_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=settings.api_prefix)
