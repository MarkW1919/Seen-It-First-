"""Unit tests for auth service — password hashing, JWT, token validation."""

import time
import uuid

from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

# ── Password hashing ────────────────────────────────────────────────────────


def test_hash_and_verify_password():
    password = "test-password-123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)


def test_verify_wrong_password():
    hashed = hash_password("correct-password")
    assert not verify_password("wrong-password", hashed)


def test_hash_is_not_deterministic():
    """bcrypt salts produce different hashes for the same input."""
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2


def test_verify_empty_password_fails():
    hashed = hash_password("real-password")
    assert not verify_password("", hashed)


def test_hash_long_password():
    long_pw = "a" * 200
    hashed = hash_password(long_pw)
    assert verify_password(long_pw, hashed)


# ── JWT tokens ───────────────────────────────────────────────────────────────


def test_create_and_decode_access_token():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "agent")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "agent"
    assert payload["type"] == "access"


def test_create_and_decode_refresh_token():
    user_id = uuid.uuid4()
    token = create_refresh_token(user_id)
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "refresh"


def test_decode_invalid_token():
    payload = decode_token("not-a-valid-token")
    assert payload is None


def test_decode_tampered_token():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "agent")
    tampered = token[:20] + ("A" if token[20] != "A" else "B") + token[21:]
    payload = decode_token(tampered)
    assert payload is None


def test_access_token_contains_expiry():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "agent")
    payload = decode_token(token)
    assert "exp" in payload
    assert payload["exp"] > time.time()


def test_refresh_token_contains_expiry():
    user_id = uuid.uuid4()
    token = create_refresh_token(user_id)
    payload = decode_token(token)
    assert "exp" in payload
    assert payload["exp"] > time.time()


def test_access_token_role_preserved():
    for role in ("agent", "admin", "supervisor"):
        user_id = uuid.uuid4()
        token = create_access_token(user_id, role)
        payload = decode_token(token)
        assert payload["role"] == role


def test_access_and_refresh_tokens_differ():
    user_id = uuid.uuid4()
    access = create_access_token(user_id, "agent")
    refresh = create_refresh_token(user_id)
    assert access != refresh


def test_different_users_get_different_tokens():
    t1 = create_access_token(uuid.uuid4(), "agent")
    t2 = create_access_token(uuid.uuid4(), "agent")
    assert t1 != t2
