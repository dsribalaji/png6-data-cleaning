"""Application configuration using Pydantic Settings.

Real values come from environment variables; .env.example carries placeholders only.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application runtime settings."""

    app_name: str = "PNG6 Agentic Data Cleaning Planner"
    database_url: str = "postgresql+psycopg2://png6:changeme@db:5432/png6"
    # PROPOSED: Redis (not Valkey) as default in-memory cache/broker backend (contract §6, P2)
    redis_url: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672//"
    minio_endpoint: str = "minio:9000"
    minio_bucket: str = "png6-datasets"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    # PROPOSED: 50 MB upload limit (contract §6, P3)
    upload_max_mb: int = 50
    # PROPOSED: 5% loss limit threshold (contract §6, P3)
    loss_threshold_pct: float = 5.0
    celery_broker_url: str = "amqp://guest:guest@rabbitmq:5672//"
    celery_result_backend: str = "redis://redis:6379/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Module-level settings instance. Real values come from environment; .env.example carries placeholders only.
settings = Settings()
