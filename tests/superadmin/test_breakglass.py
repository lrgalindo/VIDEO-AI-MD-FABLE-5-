"""Tests for break-glass endpoints (SDD §8.5).

Verifies:
  - SA token → 201, audit log entry created
  - Missing auth → 403
  - Tenant JWT (not SA) → 403 (critical negative test)
  - Unknown tenant → 404
  - End session closes the audit log entry
"""

import os
import uuid
from unittest.mock import patch

import psycopg2
import pytest
from fastapi.testclient import TestClient

from cloud.main import app

client = TestClient(app, raise_server_exceptions=False)

_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/traxia",
)
_SA_SECRET = "test-platform-admin-secret-for-bg"


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
def sa_token(db):
    """Platform admin with JWT token."""
    import bcrypt
    from cloud.auth.superadmin import make_platform_admin_token

    admin_id = str(uuid.uuid4())
    pw_hash = bcrypt.hashpw(b"pw", bcrypt.gensalt(rounds=4)).decode()

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO platform_admins (id, email, password_hash, status) "
            "VALUES (%s, %s, %s, 'active')",
            (admin_id, f"bg-admin-{admin_id[:8]}@example.com", pw_hash),
        )
    db.commit()

    with patch("cloud.auth.superadmin.config") as mock_cfg:
        mock_cfg.PLATFORM_ADMIN_SECRET = _SA_SECRET
        mock_cfg.DATABASE_URL = _DB_URL
        mock_cfg.ACCESS_TOKEN_TTL_HOURS = 24
        mock_cfg.JWT_ALGORITHM = "HS256"
        token = make_platform_admin_token(admin_id)

    return {"token": token, "admin_id": admin_id}


@pytest.fixture
def tenant_id(db):
    """An active tenant for break-glass tests."""
    tid = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, name, vertical_type, status) "
            "VALUES (%s, 'BG Tenant', 'retail', 'active')",
            (tid,),
        )
    db.commit()
    return tid


def _sa_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Positive path ─────────────────────────────────────────────────────────────

def test_activate_break_glass_creates_audit_entry(sa_token, tenant_id, db):
    with patch("cloud.auth.superadmin.config") as cfg, \
         patch("cloud.superadmin.breakglass.config") as bg_cfg:
        cfg.PLATFORM_ADMIN_SECRET = _SA_SECRET
        cfg.DATABASE_URL = _DB_URL
        cfg.JWT_ALGORITHM = "HS256"
        bg_cfg.DATABASE_URL = _DB_URL

        resp = client.post(
            "/v1/superadmin/break-glass",
            json={
                "tenant_id": tenant_id,
                "reason": "Customer support escalation",
                "ticket_id": "TICKET-001",
            },
            headers=_sa_header(sa_token["token"]),
        )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["admin_id"] == sa_token["admin_id"]
    assert body["tenant_id"] == tenant_id
    assert "log_id" in body
    assert body["expires_after_hours"] == 4

    # Verify audit log entry in DB
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, reason, ticket_id, ended_at FROM break_glass_audit_log WHERE id = %s",
            (body["log_id"],),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[1] == "Customer support escalation"
    assert row[2] == "TICKET-001"
    assert row[3] is None  # not ended yet


def test_end_break_glass_closes_session(sa_token, tenant_id, db):
    """Ending a session sets ended_at."""
    with patch("cloud.auth.superadmin.config") as cfg, \
         patch("cloud.superadmin.breakglass.config") as bg_cfg:
        cfg.PLATFORM_ADMIN_SECRET = _SA_SECRET
        cfg.DATABASE_URL = _DB_URL
        cfg.JWT_ALGORITHM = "HS256"
        bg_cfg.DATABASE_URL = _DB_URL

        activate = client.post(
            "/v1/superadmin/break-glass",
            json={"tenant_id": tenant_id, "reason": "test", "ticket_id": "T-002"},
            headers=_sa_header(sa_token["token"]),
        )
        log_id = activate.json()["log_id"]

        end = client.post(
            f"/v1/superadmin/break-glass/{log_id}/end",
            headers=_sa_header(sa_token["token"]),
        )

    assert end.status_code == 200
    assert end.json()["status"] == "ended"

    with db.cursor() as cur:
        cur.execute("SELECT ended_at FROM break_glass_audit_log WHERE id = %s", (log_id,))
        row = cur.fetchone()
    assert row[0] is not None  # ended_at is set


# ── Negative path: authorization ─────────────────────────────────────────────

def test_no_auth_returns_4xx():
    """No Authorization header → 401 or 403 (depends on FastAPI version)."""
    resp = client.post(
        "/v1/superadmin/break-glass",
        json={"tenant_id": str(uuid.uuid4()), "reason": "x", "ticket_id": "y"},
    )
    assert resp.status_code in (401, 403)


def test_tenant_jwt_cannot_activate_break_glass():
    """CRITICAL: a regular tenant JWT must NOT be able to activate break-glass."""
    from cloud.auth.tokens import make_user_token

    tenant_jwt = make_user_token(
        user_id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        role="tenant_admin",
        site_ids=None,
        partner_id=None,
    )

    with patch("cloud.auth.superadmin.config") as cfg:
        cfg.PLATFORM_ADMIN_SECRET = _SA_SECRET
        cfg.DATABASE_URL = _DB_URL
        cfg.JWT_ALGORITHM = "HS256"

        resp = client.post(
            "/v1/superadmin/break-glass",
            json={
                "tenant_id": str(uuid.uuid4()),
                "reason": "malicious",
                "ticket_id": "HACK-001",
            },
            headers={"Authorization": f"Bearer {tenant_jwt}"},
        )

    # Must be 401 or 403 — never 201
    assert resp.status_code in (401, 403), (
        f"SECURITY FAILURE: tenant JWT was accepted for break-glass activation (status={resp.status_code})"
    )


def test_unknown_tenant_returns_404(sa_token):
    with patch("cloud.auth.superadmin.config") as cfg, \
         patch("cloud.superadmin.breakglass.config") as bg_cfg:
        cfg.PLATFORM_ADMIN_SECRET = _SA_SECRET
        cfg.DATABASE_URL = _DB_URL
        cfg.JWT_ALGORITHM = "HS256"
        bg_cfg.DATABASE_URL = _DB_URL

        resp = client.post(
            "/v1/superadmin/break-glass",
            json={
                "tenant_id": str(uuid.uuid4()),
                "reason": "test",
                "ticket_id": "T-999",
            },
            headers=_sa_header(sa_token["token"]),
        )

    assert resp.status_code == 404
