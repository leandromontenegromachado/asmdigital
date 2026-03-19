from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "ASM Digital"
    api_prefix: str = "/api"
    environment: str = "development"

    database_url: str = "postgresql+psycopg2://postgres:postgres@db:5432/asmdigital"

    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60 * 8

    admin_email: str = "admin@company.com"
    admin_password: str = "admin123"

    cors_origins: str = "http://localhost:3000"

    redmine_default_timeout: int = 20
    redmine_retry_attempts: int = 3
    redmine_retry_wait_seconds: int = 2
    fala_ai_teams_webhook_secret: str | None = None
    fala_ai_teams_outgoing_webhook: str | None = None
    fala_ai_teams_bot_app_id: str | None = None
    fala_ai_teams_bot_app_secret: str | None = None
    fala_ai_teams_bot_tenant_id: str = "botframework.com"
    fala_ai_teams_default_service_url: str | None = None
    fala_ai_teams_default_conversation_id: str | None = None
    fala_ai_teams_default_bot_id: str | None = None
    fala_ai_teams_fallback_user_email: str | None = None
    fala_ai_teams_fallback_user_id: str | None = None
    fala_ai_missing_checkin_cron: str = "0 16 * * 1-5"


settings = Settings()
