from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Cloud Disaster Management System"
    api_prefix: str = "/api/v1"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    postgres_user: str = "druser"
    postgres_password: str = "drpass"
    postgres_db: str = "drdb"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    redis_host: str = "redis"
    redis_port: int = 6379

    celery_broker_db: int = 0
    celery_backend_db: int = 1

    health_check_timeout_seconds: float = 2.0
    health_check_retry_count: int = 3
    health_check_retry_backoff_seconds: float = 0.5

    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_reset_timeout_seconds: int = 30

    primary_region: str = "region-a"
    secondary_region: str = "region-b"

    backup_schedule_minutes: int = 5
    object_store_path: str = "./object_store"

    monitoring_enabled: bool = True
    monitoring_interval_seconds: int = 15
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:8000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"

    @property
    def celery_broker_url(self) -> str:
        return f"{self.redis_url}/{self.celery_broker_db}"

    @property
    def celery_result_backend(self) -> str:
        return f"{self.redis_url}/{self.celery_backend_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
