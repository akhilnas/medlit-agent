from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://medlit:medlit@localhost:5432/medlit"
    redis_url: str = "redis://localhost:6379/0"
    debug: bool = False
    ncbi_api_key: str | None = None
    gemini_api_key: str | None = None
    embedding_model_name: str = "NeuML/pubmedbert-base-embeddings"

    # API authentication (set to enable; leave unset for local dev)
    api_key: str | None = None

    # Scheduler
    scheduler_enabled: bool = True

    # Notifications (optional — gracefully no-ops when not set)
    slack_webhook_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_address: str | None = None
    notification_email_to: str | None = None


settings = Settings()
