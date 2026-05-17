from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "taskflow-service"
    service_port: int = 8200
    environment: str = "dev"

    postgres_dsn: str = "postgresql+psycopg://taskflow:taskflow@postgres:5432/taskflow"
    redis_url: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    storage_endpoint: str = "minio:9000"
    storage_access_key: str = "minioadmin"
    storage_secret_key: str = "minioadmin"
    storage_bucket: str = "taskflow"

    jwt_secret: str = "taskflow-dev-secret"
    encryption_key: str = "taskflow-dev-encryption-key"

    board_load_target_ms: int = 2000
    forecast_mape_target: float = 10.0
    concurrent_users_target: int = 5000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
