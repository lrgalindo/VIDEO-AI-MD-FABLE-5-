"""HTTP-layer tests for tenant lifecycle endpoints (Sección 3.1 decisión 11).

These tests use FastAPI TestClient and a real local PostgreSQL database
(DATABASE_URL env var or default dev connection).  Setup rows are committed
so they are visible to the TestClient's independent psycopg2 connections;
teardown uses explicit DELETEs (same pattern as tests/backoffice/).

Running:
    PLATFORM_ADMIN_SECRET=test-secret \\
    DATABASE_URL=postgresql://rodrigogalindo@localhost:5432/traxia \\
    pytest tests/lifecycle/test_lifecycle_api.py -v

Coverage:
  (a) POST /v1/tenants/register          — creates tenant status='onboarding'
  (b) POST /v1/superadmin/tenants/{id}/approve — SuperAdmin activates tenant,
        returns one-time activation code; activation_code stored as hash only
  (c) POST /v1/superadmin/tenants/{id}/deactivate — SuperAdmin makes inactive,
        revokes all gateways; revoked gateway cannot refresh

  Negative tests:
  - Tenant token (admin role) cannot call approve → 401/403 (wrong signature)
  - Onboarding tenant gateway cannot activate → 401 (tenant.status check)
  - Revoked gateway cannot refresh → 401 (Fase 1 §8.7.0 status check)
  - Approve already-active tenant → 404
"""

import os
import uuid
from typing import Generator

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

from cloud.auth.superadmin import make_platform_admin_token
from cloud.auth.tokens import make_user_token, new_opaque_token, sha256_hex
from cloud.main import app

_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://rodrigogalindo@localhost:5432/traxia",
)

client = TestClient(app, raise_server_exceptions=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uid() -> str:
    return str(uuid.uuid4())


def _sa_header(admin_id: str) -> dict:
    return {"Authorization": f"Bearer {make_platform_admin_token(admin_id)}"}


def _user_header(user_id: str, tenant_id: str, role: str = "admin") -> dict:
    return {"Authorization": f"Bearer {make_user_token(user_id, tenant_id, role)}"}


# ── Module fixture — committed rows visible to TestClient connections ──────────

@pytest.fixture(scope="module")
def db() -> Generator[psycopg2.extras.RealDictCursor, None, None]:
    conn = psycopg2.connect(_DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    cur = conn.cursor()
    yield cur
    conn.rollback()
    conn.close()


@pytest.fixture(scope="module")
def seed(db: psycopg2.extras.RealDictCursor):
    """Commit shared test rows so they are visible across connections.

    require_platform_admin opens its OWN psycopg2 connection; rows must be
    committed before the TestClient calls the SA endpoints.
    """
    admin_id = _uid()
    reseller_id = _uid()

    db.execute(
        "INSERT INTO platform_admins (id, email, status) VALUES (%s, %s, 'active')",
        (admin_id, f"sa-{admin_id[:8]}@traxia-test.com"),
    )
    db.execute(
        "INSERT INTO resellers (id, name, status) VALUES (%s, %s, 'active')",
        (reseller_id, f"Reseller {reseller_id[:8]}"),
    )
    db.connection.commit()

    yield {"admin_id": admin_id, "reseller_id": reseller_id}

    # Teardown — delete in dependency order; tenants cascade to sites/gateways
    # (actual tenant rows created per-test; clean them up here generically)
    db.execute(
        "DELETE FROM edge_gateways eg USING sites s "
        "WHERE eg.site_id = s.id AND s.tenant_id IN "
        "(SELECT id FROM tenants WHERE reseller_id = %s)",
        (reseller_id,),
    )
    db.execute("DELETE FROM sites WHERE tenant_id IN (SELECT id FROM tenants WHERE reseller_id = %s)", (reseller_id,))
    db.execute("DELETE FROM tenants WHERE reseller_id = %s", (reseller_id,))
    db.execute("DELETE FROM resellers WHERE id = %s", (reseller_id,))
    db.execute("DELETE FROM platform_admins WHERE id = %s", (admin_id,))
    db.connection.commit()


# ── (a) Registration ──────────────────────────────────────────────────────────

def test_register_creates_onboarding_tenant():
    resp = client.post(
        "/v1/tenants/register",
        json={
            "name": "Acme Retail",
            "contact_email": "contact@acme-retail.com",
            "vertical_type": "retail",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "onboarding"
    assert "tenant_id" in body


def test_register_invalid_vertical_type():
    resp = client.post(
        "/v1/tenants/register",
        json={
            "name": "Bad Vertical",
            "contact_email": "bv@test.com",
            "vertical_type": "healthcare",
        },
    )
    assert resp.status_code == 422


# ── (b) Approval ──────────────────────────────────────────────────────────────

def test_approve_activates_tenant_and_returns_activation_code(
    db: psycopg2.extras.RealDictCursor,
    seed: dict,
):
    tenant_id = _uid()
    db.execute(
        "INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) "
        "VALUES (%s, %s, 'Approve Test Tenant', 'retail', 'onboarding', 'at@test.com')",
        (tenant_id, seed["reseller_id"]),
    )
    db.connection.commit()

    gateway_id = f"gw-test-{_uid()[:8]}"
    resp = client.post(
        f"/v1/superadmin/tenants/{tenant_id}/approve",
        json={"gateway_id": gateway_id, "vertical_type": "retail"},
        headers=_sa_header(seed["admin_id"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "active"
    assert body["gateway_id"] == gateway_id
    assert len(body["activation_code"]) > 20

    # Verify activation_code is stored as hash only
    db.execute(
        "SELECT activation_code_hash FROM edge_gateways WHERE id = %s",
        (gateway_id,),
    )
    gw = db.fetchone()
    assert gw is not None
    activation_plain = body["activation_code"]
    assert gw["activation_code_hash"] == sha256_hex(activation_plain), \
        "DB must store SHA-256 hash, not plaintext"


def test_approve_returns_404_if_tenant_already_active(
    db: psycopg2.extras.RealDictCursor,
    seed: dict,
):
    tenant_id = _uid()
    db.execute(
        "INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) "
        "VALUES (%s, %s, 'Already Active', 'retail', 'active', 'aa@test.com')",
        (tenant_id, seed["reseller_id"]),
    )
    db.connection.commit()

    resp = client.post(
        f"/v1/superadmin/tenants/{tenant_id}/approve",
        json={"gateway_id": f"gw-{_uid()[:8]}", "vertical_type": "retail"},
        headers=_sa_header(seed["admin_id"]),
    )
    assert resp.status_code == 404


def test_approve_requires_superadmin_token__tenant_token_rejected(
    db: psycopg2.extras.RealDictCursor,
    seed: dict,
):
    """NEGATIVE: a regular tenant admin JWT must not call approve (no 'sa' claim)."""
    tenant_id = _uid()
    db.execute(
        "INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) "
        "VALUES (%s, %s, 'Negative Approve', 'retail', 'onboarding', 'na@test.com')",
        (tenant_id, seed["reseller_id"]),
    )
    db.connection.commit()
    non_admin_token = _user_header(_uid(), tenant_id, "admin")

    resp = client.post(
        f"/v1/superadmin/tenants/{tenant_id}/approve",
        json={"gateway_id": f"gw-{_uid()[:8]}", "vertical_type": "retail"},
        headers=non_admin_token,
    )
    # Tenant tokens are signed with JWT_SECRET; the SA endpoint decodes with
    # PLATFORM_ADMIN_SECRET — the signature fails → 401/403
    assert resp.status_code in (401, 403), (
        f"Expected 401/403 for tenant token on SA endpoint, got {resp.status_code}"
    )


# ── NEGATIVE: onboarding gateway cannot activate ─────────────────────────────

def test_onboarding_tenant_gateway_cannot_activate(
    db: psycopg2.extras.RealDictCursor,
    seed: dict,
):
    """NEGATIVE: gateway for an onboarding tenant cannot exchange activation code."""
    tenant_id = _uid()
    site_id = _uid()
    gateway_id = f"gw-onb-{_uid()[:8]}"
    activation_plain, activation_hash = new_opaque_token()

    db.execute(
        "INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) "
        "VALUES (%s, %s, 'Onboarding Block Test', 'retail', 'onboarding', 'ob@test.com')",
        (tenant_id, seed["reseller_id"]),
    )
    db.execute(
        "INSERT INTO sites (id, tenant_id, name, status) VALUES (%s, %s, 'S', 'active')",
        (site_id, tenant_id),
    )
    db.execute(
        """
        INSERT INTO edge_gateways
            (id, site_id, vertical_type, status,
             activation_code_hash, activation_code_expires_at)
        VALUES (%s, %s, 'retail', 'offline', %s, now() + interval '72 hours')
        """,
        (gateway_id, site_id, activation_hash),
    )
    db.connection.commit()

    resp = client.post(
        "/v1/edge/token/activate",
        json={"gateway_id": gateway_id, "activation_code": activation_plain},
    )
    # EXISTS (tenant.status = 'active') sub-query blocks the UPDATE → 0 rows → 401
    assert resp.status_code == 401, (
        f"Onboarding tenant gateway must not activate; got {resp.status_code}"
    )


# ── (c) Deactivation ─────────────────────────────────────────────────────────

def test_deactivate_sets_inactive_and_revokes_gateways(
    db: psycopg2.extras.RealDictCursor,
    seed: dict,
):
    tenant_id = _uid()
    site_id = _uid()
    gw1_id = f"gw-deact1-{_uid()[:8]}"
    gw2_id = f"gw-deact2-{_uid()[:8]}"
    _, rh1 = new_opaque_token()
    _, rh2 = new_opaque_token()

    db.execute(
        "INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) "
        "VALUES (%s, %s, 'Deactivation Tenant', 'retail', 'active', 'dt@test.com')",
        (tenant_id, seed["reseller_id"]),
    )
    db.execute(
        "INSERT INTO sites (id, tenant_id, name, status) VALUES (%s, %s, 'DS', 'active')",
        (site_id, tenant_id),
    )
    for gw_id, rh in [(gw1_id, rh1), (gw2_id, rh2)]:
        db.execute(
            """
            INSERT INTO edge_gateways
                (id, site_id, vertical_type, status,
                 refresh_token_hash, refresh_token_expires_at)
            VALUES (%s, %s, 'retail', 'online', %s, now() + interval '90 days')
            """,
            (gw_id, site_id, rh),
        )
    db.connection.commit()

    resp = client.post(
        f"/v1/superadmin/tenants/{tenant_id}/deactivate",
        headers=_sa_header(seed["admin_id"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "inactive"
    assert body["gateways_revoked"] == 2

    # Verify tenant is inactive in DB
    db.execute("SELECT status FROM tenants WHERE id = %s", (tenant_id,))
    assert db.fetchone()["status"] == "inactive"

    # Verify both gateways are revoked with NULL token hashes
    db.execute(
        "SELECT id, status, refresh_token_hash FROM edge_gateways "
        "WHERE id = ANY(%s)",
        ([gw1_id, gw2_id],),
    )
    rows = db.fetchall()
    assert len(rows) == 2
    for row in rows:
        assert row["status"] == "revoked"
        assert row["refresh_token_hash"] is None, \
            "refresh_token_hash must be NULL after revocation"


def test_deactivate_requires_superadmin(
    db: psycopg2.extras.RealDictCursor,
    seed: dict,
):
    """NEGATIVE: tenant admin token cannot call deactivate."""
    tenant_id = _uid()
    db.execute(
        "INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) "
        "VALUES (%s, %s, 'Deact Neg', 'retail', 'active', 'dn@test.com')",
        (tenant_id, seed["reseller_id"]),
    )
    db.connection.commit()

    resp = client.post(
        f"/v1/superadmin/tenants/{tenant_id}/deactivate",
        headers=_user_header(_uid(), tenant_id, "admin"),
    )
    assert resp.status_code in (401, 403)


def test_revoked_gateway_cannot_refresh(
    db: psycopg2.extras.RealDictCursor,
    seed: dict,
):
    """NEGATIVE: Fase 1 §8.7.0 — revoked gateway is blocked at /refresh."""
    tenant_id = _uid()
    site_id = _uid()
    gw_id = f"gw-rev-{_uid()[:8]}"
    refresh_plain, refresh_hash = new_opaque_token()

    db.execute(
        "INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) "
        "VALUES (%s, %s, 'Revoked GW Test', 'retail', 'inactive', 'rg@test.com')",
        (tenant_id, seed["reseller_id"]),
    )
    db.execute(
        "INSERT INTO sites (id, tenant_id, name, status) VALUES (%s, %s, 'RGS', 'active')",
        (site_id, tenant_id),
    )
    db.execute(
        """
        INSERT INTO edge_gateways
            (id, site_id, vertical_type, status,
             refresh_token_hash, refresh_token_expires_at)
        VALUES (%s, %s, 'retail', 'revoked', %s, now() + interval '90 days')
        """,
        (gw_id, site_id, refresh_hash),
    )
    db.connection.commit()

    resp = client.post(
        "/v1/edge/token/refresh",
        json={"gateway_id": gw_id, "refresh_token": refresh_plain},
    )
    assert resp.status_code == 401, (
        f"Revoked gateway must not refresh; got {resp.status_code}"
    )
