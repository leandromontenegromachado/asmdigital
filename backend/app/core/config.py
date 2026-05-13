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
    app_public_url: str = "http://localhost:3000"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_pass: str | None = None
    smtp_from: str = "asmdigital@company.com"
    smtp_use_tls: bool = True

    redmine_default_timeout: int = 20
    redmine_retry_attempts: int = 3
    redmine_retry_wait_seconds: int = 2
    scheduler_timezone: str = "America/Sao_Paulo"
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
    fala_ai_participant_roles: str = "funcionario,gerente,viewer"
    fala_ai_assistant_enabled: bool = True
    fala_ai_assistant_domain: str = "geral"
    fala_ai_gemini_api_key: str | None = None
    fala_ai_gemini_model: str = "gemini-3-flash-preview"
    fala_ai_gemini_timeout_seconds: int = 60
    ai_http_verify_ssl: bool = True
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str | None = None
    openrouter_app_name: str = "ASM Digital"


settings = Settings()
