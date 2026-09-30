"""Application settings (pydantic-settings, Backend.md)."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "planner"
    database_url: str = "sqlite+aiosqlite:///./planner.db"
    celery_broker_url: str = Field(
        default="amqp://guest:guest@localhost:5672//",
        validation_alias=AliasChoices("celery_broker_url", "rabbitmq_url"),
    )
    celery_task_always_eager: bool = True
    redis_url: str = "redis://localhost:6379/0"
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_root: str = "./storage"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "planner"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    jwt_secret: str = "dev-only-insecure-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 7
    fernet_key: str = ""
    upload_max_mb: int = 50
    loss_threshold_default: float = 0.05
    n8n_folder_poll_minutes: int = 5
    n8n_folder_path: str = "./n8n_folder"
    cors_origins: list[str] | str = ["http://localhost:5173"]
    groq_api_key: str | None = None
    log_level: str = "INFO"
    environment: str = "local"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    @field_validator("cors_origins", mode="after")
    @classmethod
    def _parse_cors_origins(cls, v: list[str] | str) -> list[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("["):
                try:
                    parsed = json.loads(v_str)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed]
                except Exception:
                    pass
            return [x.strip() for x in v_str.split(",") if x.strip()]
        return v

    @property
    def rabbitmq_url(self) -> str:
        """Alias for celery_broker_url for backwards compatibility."""
        return self.celery_broker_url


settings = Settings()
