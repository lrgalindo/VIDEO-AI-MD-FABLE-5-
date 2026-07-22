"""Tests for POST /v1/superadmin/login (SDD §3.1 decision 11b).

Verifies:
  - Valid email+password → 200 with JWT bearing {"sa": true}
  - Wrong password → 401 (invalid_credentials)
  - Unknown email → 401 (same error, no email enumeration)
  - Disabled admin → 401
  - PLATFORM_ADMIN_SECRET not set → 503

The make_platform_admin_token() bootstrap function is implicitly tested here
because the login endpoint uses it to issue the token.
"""

import os
import uuid

import bcrypt
import jwt
import psycopg2
import pytest
from fastapi.testclient import TestClient

from cloud.main import app

client = TestClient(app, raise_server_exceptions=False)

_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/traxia",
)
_SA_SECRET = "test-platform-admin-secret"


@pytest.fixture
def db():
    conn = psycopg2.connect(_DB_URL)
    conn.autocommit = False
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def active_admin(db):
    admin_id = str(uuid.uuid4())
    password = "SecurePass123!"
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO platform_admins (id, email, password_hash, status) "
            "VALUES (%s, %s, %s, 'active')",
            (admin_id, f"admin-{admin_id[:8]}@example.com", pw_hash),
        )
    db.commit()

    return {"id": admin_id, "email": f"admin-{admin_id[:8]}@example.com", "password": password}


@pytest.fixture
def disabled_admin(db):
    admin_id = str(uuid.uuid4())
    pw_hash = bcrypt.hashpw(b"anypass", bcrypt.gensalt(rounds=4)).decode()

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO platform_admins (id, email, password_hash, status) "
            "VALUES (%s, %s, %s, 'disabled')",
            (admin_id, f"disabled-{admin_id[:8]}@example.com", pw_hash),
        )
    db.commit()

    return {"id": admin_id, "email": f"disabled-{admin_id[:8]}@example.com", "password": "anypass"}


def test_valid_login_returns_jwt(active_admin):
    from unittest.mock import patch

    with patch("cloud.auth.superadmin.config") as mock_cfg:
        mock_cfg.PLATFORM_ADMIN_SECRET = _SA_SECRET
        mock_cfg.DATABASE_URL = _DB_URL
        mock_cfg.ACCESS_TOKEN_TTL_HOURS = 24
        mock_cfg.JWT_ALGORITHM = "HS256"

        resp = client.post(
            "/v1/superadmin/login",
            json={"email": active_admin["email"], "password": active_admin["password"]},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"

    payload = jwt.decode(body["access_token"], _SA_SECRET, algorithms=["HS256"])
    assert payload["sa"] is True
    assert payload["sub"] == active_admin["id"]


def test_wrong_password_returns_401(active_admin):
    from unittest.mock import patch

    with patch("cloud.auth.superadmin.config") as mock_cfg:
        mock_cfg.PLATFORM_ADMIN_SECRET = _SA_SECRET
        mock_cfg.DATABASE_URL = _DB_URL
        mock_cfg.ACCESS_TOKEN_TTL_HOURS = 24
        mock_cfg.JWT_ALGORITHM = "HS256"

        resp = client.post(
            "/v1/superadmin/login",
            json={"email": active_admin["email"], "password": "WrongPassword!"},
        )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_credentials"


def test_unknown_email_returns_401():
    from unittest.mock import patch

    with patch("cloud.auth.superadmin.config") as mock_cfg:
        mock_cfg.PLATFORM_ADMIN_SECRET = _SA_SECRET
        mock_cfg.DATABASE_URL = _DB_URL
        mock_cfg.ACCESS_TOKEN_TTL_HOURS = 24
        mock_cfg.JWT_ALGORITHM = "HS256"

        resp = client.post(
            "/v1/superadmin/login",
            json={"email": "nobody@nowhere-test.example.com", "password": "irrelevant"},
        )

    assert resp.status_code == 401
    # Same error code as wrong password — no email enumeration
    assert resp.json()["detail"] == "invalid_credentials"


def test_disabled_admin_returns_401(disabled_admin):
    from unittest.mock import patch

    with patch("cloud.auth.superadmin.config") as mock_cfg:
        mock_cfg.PLATFORM_ADMIN_SECRET = _SA_SECRET
        mock_cfg.DATABASE_URL = _DB_URL
        mock_cfg.ACCESS_TOKEN_TTL_HOURS = 24
        mock_cfg.JWT_ALGORITHM = "HS256"

        resp = client.post(
            "/v1/superadmin/login",
            json={"email": disabled_admin["email"], "password": disabled_admin["password"]},
        )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_credentials"


def test_503_when_platform_admin_secret_not_set(active_admin):
    from unittest.mock import patch

    with patch("cloud.auth.superadmin.config") as mock_cfg:
        mock_cfg.PLATFORM_ADMIN_SECRET = ""
        mock_cfg.DATABASE_URL = _DB_URL

        resp = client.post(
            "/v1/superadmin/login",
            json={"email": active_admin["email"], "password": active_admin["password"]},
        )

    assert resp.status_code == 503
