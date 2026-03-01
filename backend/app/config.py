import logging
from functools import lru_cache

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _require_env(var: str) -> str:
    """Enforce that security-critical env vars are explicitly set.

    Prevents the application from starting with weak default credentials.
    Returns a sentinel that Pydantic will override from environment.
    """
    return ""


class Settings(BaseSettings):
    # Database
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_user: str = "reposcan"
    postgres_password: str = ""  # REQUIRED — must be set via env
    postgres_db: str = "reposcan"
    postgres_sslmode: str = "prefer"  # "require" in production

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""  # Set via env for authenticated Redis

    # Auth
    secret_key: str = ""  # REQUIRED — must be set via env
    access_token_expire_minutes: int = 480  # 8 hours for field agents
    refresh_token_expire_days: int = 30

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = ""
    debug: bool = False

    # AI
    detection_confidence: float = 0.5
    plate_confidence: float = 0.6
    ocr_confidence: float = 0.7

    # Storage
    data_dir: str = "/data"
    capture_retention_days: int = 30

    @property
    def database_url(self) -> str:
        base = (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if self.postgres_sslmode and self.postgres_sslmode != "disable":
            base += f"?ssl={self.postgres_sslmode}"
        return base

    @property
    def sync_database_url(self) -> str:
        base = (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if self.postgres_sslmode and self.postgres_sslmode != "disable":
            base += f"?sslmode={self.postgres_sslmode}"
        return base

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins:
            return []
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # Block wildcard origin in production
        if "*" in origins and not self.debug:
            raise ValueError("CORS wildcard '*' is not allowed outside debug mode")
        return origins

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    # Fail-fast: refuse to start with missing critical secrets
    if not settings.secret_key:
        raise RuntimeError(
            "SECRET_KEY environment variable is required. Generate one with: openssl rand -hex 64"
        )
    if not settings.postgres_password:
        raise RuntimeError(
            "POSTGRES_PASSWORD environment variable is required. "
            "Generate one with: openssl rand -base64 32"
        )

    # Non-fatal security warnings
    if not settings.redis_password:
        logger.warning(
            "REDIS_PASSWORD is empty — Redis is accessible without authentication. "
            "Set REDIS_PASSWORD for production deployments."
        )

    if settings.debug:
        logger.warning(
            "DEBUG mode is enabled — Swagger UI (/docs) and ReDoc (/redoc) are exposed. "
            "Disable DEBUG in production environments."
        )

    if settings.postgres_sslmode == "disable" and not settings.debug:
        logger.warning(
            "POSTGRES_SSLMODE is set to 'disable' in non-debug mode. "
            "Use 'require' or 'verify-full' for production database connections."
        )

    return settings
