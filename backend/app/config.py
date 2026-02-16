from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_user: str = "reposcan"
    postgres_password: str = "change_me_in_production"
    postgres_db: str = "reposcan"

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379

    # Auth
    secret_key: str = "change-this-to-a-random-secret-key"
    access_token_expire_minutes: int = 480  # 8 hours for field agents
    refresh_token_expire_days: int = 30

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # AI
    detection_confidence: float = 0.5
    plate_confidence: float = 0.6
    ocr_confidence: float = 0.7

    # Storage
    data_dir: str = "/data"
    capture_retention_days: int = 30

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
