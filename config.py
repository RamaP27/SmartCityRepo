from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://shems:shems@localhost:5432/shems"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "dev-secret-key-change-in-production-min-32-chars"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # App
    environment: str = "development"
    debug: bool = True
    app_name: str = "SHEMS API"

    # ── Phase 3 — IoT Ecosystem ───────────────────────────────────────────────
    google_home_client_id: str = ""
    google_home_client_secret: str = ""
    google_home_project_id: str = ""

    # ── Phase 3 — Notifications ───────────────────────────────────────────────
    firebase_credentials_path: str = ""   # path to serviceAccountKey.json
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""          # E.164 e.g. "+919876543210"

    # ── Phase 3 — Kafka ───────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_grid_load_topic: str = "shems.grid.load"
    kafka_consumer_group: str = "shems-grid-consumer"

    # ── Phase 3 — DPDP Compliance ─────────────────────────────────────────────
    dpdp_audit_log_path: str = "logs/audit.jsonl"
    dpdp_data_retention_days: int = 365


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
