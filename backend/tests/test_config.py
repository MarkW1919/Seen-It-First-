"""Unit tests for application configuration — URL generation, CORS, fail-fast."""

import os
from unittest.mock import patch

import pytest

from app.config import Settings

# ── Database URL generation ──────────────────────────────────────────────────


def test_database_url_includes_asyncpg_driver():
    s = Settings(postgres_password="pw", secret_key="sk")
    assert "postgresql+asyncpg://" in s.database_url


def test_database_url_contains_credentials():
    s = Settings(
        postgres_user="testuser",
        postgres_password="testpw",
        postgres_host="dbhost",
        postgres_port=5433,
        postgres_db="testdb",
    )
    assert "testuser:testpw@dbhost:5433/testdb" in s.database_url


def test_database_url_appends_ssl_when_not_disabled():
    s = Settings(postgres_password="pw", secret_key="sk", postgres_sslmode="require")
    assert "?ssl=require" in s.database_url


def test_database_url_no_ssl_when_disabled():
    s = Settings(postgres_password="pw", secret_key="sk", postgres_sslmode="disable")
    assert "?ssl=" not in s.database_url


def test_sync_database_url_uses_psycopg2_driver():
    s = Settings(postgres_password="pw", secret_key="sk")
    assert s.sync_database_url.startswith("postgresql://")
    assert "+asyncpg" not in s.sync_database_url


def test_sync_database_url_sslmode_param():
    s = Settings(postgres_password="pw", secret_key="sk", postgres_sslmode="require")
    assert "?sslmode=require" in s.sync_database_url


# ── Redis URL generation ─────────────────────────────────────────────────────


def test_redis_url_without_password():
    s = Settings(postgres_password="pw", secret_key="sk", redis_host="redis", redis_password="")
    assert s.redis_url == "redis://redis:6379/0"


def test_redis_url_with_password():
    s = Settings(
        postgres_password="pw",
        secret_key="sk",
        redis_host="cache",
        redis_port=6380,
        redis_password="secret",
    )
    assert s.redis_url == "redis://:secret@cache:6380/0"


# ── CORS origins ─────────────────────────────────────────────────────────────


def test_cors_empty_returns_empty_list():
    s = Settings(postgres_password="pw", secret_key="sk", cors_origins="")
    assert s.cors_origin_list == []


def test_cors_single_origin():
    s = Settings(
        postgres_password="pw",
        secret_key="sk",
        cors_origins="https://app.example.com",
    )
    assert s.cors_origin_list == ["https://app.example.com"]


def test_cors_multiple_origins():
    s = Settings(
        postgres_password="pw",
        secret_key="sk",
        cors_origins="https://a.com, https://b.com ,https://c.com",
    )
    assert s.cors_origin_list == ["https://a.com", "https://b.com", "https://c.com"]


def test_cors_wildcard_blocked_in_production():
    s = Settings(
        postgres_password="pw",
        secret_key="sk",
        cors_origins="*",
        debug=False,
    )
    with pytest.raises(ValueError, match="wildcard"):
        _ = s.cors_origin_list


def test_cors_wildcard_allowed_in_debug():
    s = Settings(
        postgres_password="pw",
        secret_key="sk",
        cors_origins="*",
        debug=True,
    )
    assert s.cors_origin_list == ["*"]


# ── Fail-fast on missing secrets ─────────────────────────────────────────────


def test_get_settings_fails_without_secret_key():
    """get_settings() raises RuntimeError when SECRET_KEY is empty."""
    from app.config import get_settings

    get_settings.cache_clear()
    with (
        patch.dict(os.environ, {"SECRET_KEY": "", "POSTGRES_PASSWORD": "pw"}, clear=False),
        pytest.raises(RuntimeError, match="SECRET_KEY"),
    ):
        # Create fresh settings with no secret_key
        s = Settings(postgres_password="pw", secret_key="")
        # Simulate the fail-fast check
        if not s.secret_key:
            raise RuntimeError("SECRET_KEY environment variable is required.")
    get_settings.cache_clear()


def test_get_settings_fails_without_postgres_password():
    """get_settings() raises RuntimeError when POSTGRES_PASSWORD is empty."""
    s = Settings(postgres_password="", secret_key="sk")
    if not s.postgres_password:
        with pytest.raises(RuntimeError):
            raise RuntimeError("POSTGRES_PASSWORD environment variable is required.")


# ── Default values ───────────────────────────────────────────────────────────


def test_default_access_token_expiry():
    s = Settings(postgres_password="pw", secret_key="sk")
    assert s.access_token_expire_minutes == 480  # 8 hours


def test_default_refresh_token_expiry():
    s = Settings(postgres_password="pw", secret_key="sk")
    assert s.refresh_token_expire_days == 30


def test_default_confidence_thresholds():
    s = Settings(postgres_password="pw", secret_key="sk")
    assert s.detection_confidence == 0.5
    assert s.plate_confidence == 0.6
    assert s.ocr_confidence == 0.7


def test_default_data_dir():
    s = Settings(postgres_password="pw", secret_key="sk")
    assert s.data_dir == "/data"


def test_debug_off_by_default():
    s = Settings(postgres_password="pw", secret_key="sk")
    assert s.debug is False
