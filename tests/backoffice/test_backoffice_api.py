"""HTTP-layer tests for backoffice endpoints (Fase 2).

These tests use FastAPI TestClient and a real local PostgreSQL database
(DATABASE_URL env var or the default dev connection).  Each test function
creates its own UUIDs and cleans up in teardown, so tests are idempotent.

Running:
    DATABASE_URL=postgresql://rodrigogalindo@localhost:5432/traxia pytest tests/backoffice/test_backoffice_api.py -v

Coverage:
  - POST /v1/backoffice/users — admin creates operator user + site assignments
  - GET  /v1/backoffice/users — admin lists users
  - POST /v1/backoffice/partners — admin creates partner + zones + invite
  - POST /v1/backoffice/partners/{id}/revoke — manual revocation
  - Negative: Partner Viewer JWT → 403 on user/partner endpoints
  - Negative: Gateway JWT (no 'tid') → 401 on backoffice endpoints
  - Negative: Operator JWT → 403 on management endpoints
"""

import os
import uuid
from typing import Generator

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

from cloud.auth.tokens import make_user_token
from cloud.main import app
from tests.helpers import encrypt_test_rtsp

# ── Test DB connection (runs as postgres superuser for setup/teardown) ─────────
_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://rodrigogalindo@localhost:5432/traxia",
)

client = TestClient(app)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())


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
    """Insert module-level test fixtures and clean up after all tests in module."""
    tenant_id = _new_id()
    site_id = _new_id()
    camera_id = _new_id()
    admin_user_id = _new_id()
    reseller_id = _new_id()

    db.execute(
        "INSERT INTO resellers (id, name) VALUES (%s, 'BT Reseller')",
        (reseller_id,),
    )
    db.execute(
        "INSERT INTO tenants (id, reseller_id, name, vertical_type, status) "
        "VALUES (%s, %s, 'BT Tenant', 'retail', 'active')",
        (tenant_id, reseller_id),
    )
    db.execute(
        "INSERT INTO sites (id, tenant_id, name, status) "
        "VALUES (%s, %s, 'BT Site', 'active')",
        (site_id, tenant_id),
    )
    db.execute(
        "INSERT INTO cameras (id, site_id, name, rtsp_url_ciphertext, rtsp_url_key_id, status) "
        "VALUES (%s, %s, 'BT Cam', %s, 'test-key-v1', 'active')",
        (camera_id, site_id, psycopg2.Binary(encrypt_test_rtsp())),
    )
    db.execute(
        "INSERT INTO users (id, tenant_id, email, role, status) "
        "VALUES (%s, %s, 'admin@bt.com', 'admin', 'active')",
        (admin_user_id, tenant_id),
    )
    db.connection.commit()

    data = {
        "tenant_id": tenant_id,
        "site_id": site_id,
        "camera_id": camera_id,
        "admin_user_id": admin_user_id,
    }
    yield data

    # Teardown: delete in reverse dependency order
    db.execute("DELETE FROM user_site_assignments WHERE site_id = %s", (site_id,))
    db.execute("DELETE FROM zone_dwell_sessions WHERE zone_id IN (SELECT id FROM zones WHERE camera_id = %s)", (camera_id,))
    db.execute("DELETE FROM zones WHERE camera_id = %s", (camera_id,))
    db.execute("DELETE FROM users WHERE tenant_id = %s", (tenant_id,))
    db.execute("DELETE FROM partners WHERE tenant_id = %s", (tenant_id,))
    db.execute("DELETE FROM cameras WHERE id = %s", (camera_id,))
    db.execute("DELETE FROM sites WHERE id = %s", (site_id,))
    db.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
    db.execute("DELETE FROM resellers WHERE id = %s", (reseller_id,))
    db.connection.commit()


def _admin_headers(seed: dict) -> dict:
    token = make_user_token(
        user_id=seed["admin_user_id"],
        tenant_id=seed["tenant_id"],
        role="admin",
    )
    return {"Authorization": f"Bearer {token}"}


def _partner_viewer_headers(seed: dict, partner_id: str, user_id: str) -> dict:
    token = make_user_token(
        user_id=user_id,
        tenant_id=seed["tenant_id"],
        role="viewer",
        partner_id=partner_id,
    )
    return {"Authorization": f"Bearer {token}"}


def _operator_headers(seed: dict, user_id: str, site_ids: list) -> dict:
    token = make_user_token(
        user_id=user_id,
        tenant_id=seed["tenant_id"],
        role="operator",
        site_ids=site_ids,
    )
    return {"Authorization": f"Bearer {token}"}


def _gateway_headers() -> dict:
    """Simulate a gateway JWT (has 'sid'/'vt', lacks 'tid') — should be 401."""
    from cloud.auth.tokens import make_access_token
    token = make_access_token(
        gateway_id="gw-bt-test",
        site_id=_new_id(),
        vertical_type="retail",
    )
    return {"Authorization": f"Bearer {token}"}


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestCreateUser:
    def test_admin_creates_operator(self, seed: dict) -> None:
        resp = client.post(
            "/v1/backoffice/users",
            json={
                "email": "op-bt@test.com",
                "role": "operator",
                "site_ids": [seed["site_id"]],
            },
            headers=_admin_headers(seed),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["role"] == "operator"
        assert body["site_ids"] == [seed["site_id"]]
        assert "invite_token" in body
        assert len(body["invite_token"]) > 10

    def test_admin_creates_viewer(self, seed: dict) -> None:
        resp = client.post(
            "/v1/backoffice/users",
            json={
                "email": "viewer-bt@test.com",
                "role": "viewer",
                "site_ids": [seed["site_id"]],
            },
            headers=_admin_headers(seed),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["role"] == "viewer"

    def test_admin_lists_users(self, seed: dict) -> None:
        resp = client.get("/v1/backoffice/users", headers=_admin_headers(seed))
        assert resp.status_code == 200, resp.text
        users = resp.json()
        emails = [u["email"] for u in users]
        assert "admin@bt.com" in emails

    def test_invalid_role_rejected(self, seed: dict) -> None:
        resp = client.post(
            "/v1/backoffice/users",
            json={"email": "x@bt.com", "role": "admin", "site_ids": [seed["site_id"]]},
            headers=_admin_headers(seed),
        )
        assert resp.status_code == 422

    def test_empty_site_ids_rejected(self, seed: dict) -> None:
        resp = client.post(
            "/v1/backoffice/users",
            json={"email": "x2@bt.com", "role": "operator", "site_ids": []},
            headers=_admin_headers(seed),
        )
        assert resp.status_code == 422

    def test_cross_tenant_site_rejected(self, seed: dict) -> None:
        """Assigning a user to a site in another tenant is rejected by RLS (403)."""
        other_site = _new_id()  # random UUID that doesn't belong to this tenant
        resp = client.post(
            "/v1/backoffice/users",
            json={"email": f"cross{_new_id()[:8]}@bt.com", "role": "viewer",
                  "site_ids": [other_site]},
            headers=_admin_headers(seed),
        )
        assert resp.status_code == 403


class TestCreatePartner:
    def test_admin_creates_partner_with_zones(self, seed: dict) -> None:
        resp = client.post(
            "/v1/backoffice/partners",
            json={
                "name": "BT Partner SA",
                "admin_email": "partner-admin@bt.com",
                "access_expires_at": "2030-01-01T00:00:00Z",
                "zones": [{
                    "camera_id": seed["camera_id"],
                    "name": "BT Shelf Zone",
                    "zone_type": "shelf",
                    "coordinates": {"type": "polygon", "points": [[0,0],[100,0],[100,100],[0,100]]},
                }],
            },
            headers=_admin_headers(seed),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["zones_created"] == 1
        assert "invite_token" in body
        assert "partner_id" in body

    def test_staff_exclusion_zone_allowed(self, seed: dict) -> None:
        resp = client.post(
            "/v1/backoffice/partners",
            json={
                "name": "BT Partner Staff",
                "admin_email": f"staff-{_new_id()[:6]}@bt.com",
                "zones": [{
                    "camera_id": seed["camera_id"],
                    "name": "Staff Lounge",
                    "zone_type": "staff_exclusion",
                    "coordinates": {"points": []},
                }],
            },
            headers=_admin_headers(seed),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["zones_created"] == 1

    def test_cross_tenant_camera_rejected(self, seed: dict) -> None:
        other_camera = _new_id()
        resp = client.post(
            "/v1/backoffice/partners",
            json={
                "name": "Cross Tenant P",
                "admin_email": f"ct{_new_id()[:6]}@bt.com",
                "zones": [{
                    "camera_id": other_camera,
                    "name": "Zone X",
                    "zone_type": "shelf",
                    "coordinates": {},
                }],
            },
            headers=_admin_headers(seed),
        )
        assert resp.status_code == 403


class TestPartnerRevocation:
    def test_manual_revoke(self, seed: dict, db: psycopg2.extras.RealDictCursor) -> None:
        # Create a partner via the API first
        resp = client.post(
            "/v1/backoffice/partners",
            json={
                "name": "Revoke Partner",
                "admin_email": f"rv{_new_id()[:6]}@bt.com",
            },
            headers=_admin_headers(seed),
        )
        assert resp.status_code == 201, resp.text
        partner_id = resp.json()["partner_id"]

        # Revoke via endpoint
        rev = client.post(
            f"/v1/backoffice/partners/{partner_id}/revoke",
            headers=_admin_headers(seed),
        )
        assert rev.status_code == 200, rev.text
        assert rev.json()["revoked"] == partner_id

        # Verify in DB (superuser read, bypasses RLS)
        db.execute("SELECT status FROM partners WHERE id = %s", (partner_id,))
        row = db.fetchone()
        assert row is not None
        assert row["status"] == "inactive"

    def test_auto_revocation_same_path(self, seed: dict) -> None:
        """Verify the scheduler's revoke_partner() function works identically."""
        from cloud.backoffice.scheduler import revoke_partner

        # Create partner directly in DB (superuser)
        partner_id = _new_id()
        conn = psycopg2.connect(_DB_URL)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO partners (id, tenant_id, name, status, access_expires_at) "
                        "VALUES (%s, %s, 'Auto Revoke Partner', 'active', now() - interval '1 second')",
                        (partner_id, seed["tenant_id"]),
                    )
        finally:
            conn.close()

        # Call the shared revocation function (same as scheduler uses)
        revoke_partner(partner_id, seed["tenant_id"])

        # Verify
        conn2 = psycopg2.connect(_DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            with conn2:
                with conn2.cursor() as cur:
                    cur.execute("SELECT status FROM partners WHERE id = %s", (partner_id,))
                    row = cur.fetchone()
                    assert row["status"] == "inactive"
        finally:
            conn2.close()


class TestNegativeAccessControl:
    """Verify Partner Viewer + Operator + Gateway tokens cannot reach admin endpoints."""

    @pytest.fixture(autouse=True)
    def _partner_context(self, seed: dict, db: psycopg2.extras.RealDictCursor):
        """Create a partner + viewer user for the negative tests."""
        partner_id = _new_id()
        viewer_id = _new_id()
        db.execute(
            "INSERT INTO partners (id, tenant_id, name, status) "
            "VALUES (%s, %s, 'Negative Test Partner', 'active')",
            (partner_id, seed["tenant_id"]),
        )
        db.execute(
            "INSERT INTO users (id, tenant_id, partner_id, email, role, status) "
            "VALUES (%s, %s, %s, 'pv-neg@bt.com', 'viewer', 'active')",
            (viewer_id, seed["tenant_id"], partner_id),
        )
        db.connection.commit()
        self._partner_id = partner_id
        self._viewer_id = viewer_id
        self._seed = seed
        yield
        db.execute("DELETE FROM users WHERE id = %s", (viewer_id,))
        db.execute("DELETE FROM partners WHERE id = %s", (partner_id,))
        db.connection.commit()

    def _pv_headers(self) -> dict:
        return _partner_viewer_headers(self._seed, self._partner_id, self._viewer_id)

    def test_partner_viewer_cannot_create_user(self) -> None:
        resp = client.post(
            "/v1/backoffice/users",
            json={"email": "x@x.com", "role": "viewer",
                  "site_ids": [self._seed["site_id"]]},
            headers=self._pv_headers(),
        )
        assert resp.status_code == 403, f"Expected 403 got {resp.status_code}: {resp.text}"

    def test_partner_viewer_cannot_list_users(self) -> None:
        resp = client.get("/v1/backoffice/users", headers=self._pv_headers())
        assert resp.status_code == 403, f"Expected 403 got {resp.status_code}: {resp.text}"

    def test_partner_viewer_cannot_create_partner(self) -> None:
        resp = client.post(
            "/v1/backoffice/partners",
            json={"name": "Hack Partner", "admin_email": "h@h.com"},
            headers=self._pv_headers(),
        )
        assert resp.status_code == 403, f"Expected 403 got {resp.status_code}: {resp.text}"

    def test_partner_viewer_cannot_revoke_partner(self) -> None:
        resp = client.post(
            f"/v1/backoffice/partners/{self._partner_id}/revoke",
            headers=self._pv_headers(),
        )
        assert resp.status_code == 403, f"Expected 403 got {resp.status_code}: {resp.text}"

    def test_operator_cannot_create_user(self) -> None:
        op_id = _new_id()
        headers = _operator_headers(self._seed, op_id, [self._seed["site_id"]])
        resp = client.post(
            "/v1/backoffice/users",
            json={"email": "x@x.com", "role": "viewer",
                  "site_ids": [self._seed["site_id"]]},
            headers=headers,
        )
        assert resp.status_code == 403, f"Expected 403 got {resp.status_code}: {resp.text}"

    def test_operator_cannot_create_partner(self) -> None:
        op_id = _new_id()
        headers = _operator_headers(self._seed, op_id, [self._seed["site_id"]])
        resp = client.post(
            "/v1/backoffice/partners",
            json={"name": "Hack", "admin_email": "op@h.com"},
            headers=headers,
        )
        assert resp.status_code == 403, f"Expected 403 got {resp.status_code}: {resp.text}"

    def test_partner_admin_cannot_create_tenant_user(self) -> None:
        """Partner Admin (role='admin' + pid present) is blocked by the pid check in
        require_tenant_admin — even though role=='admin', pid is not None so the
        dependency rejects with 403.  This is the case that specifically exercises
        the 'pid is not None' branch, distinct from the Partner Viewer test."""
        token = make_user_token(
            user_id=self._viewer_id,       # reuse any user_id; what matters are role+pid
            tenant_id=self._seed["tenant_id"],
            role="admin",                  # admin role, but partner-scoped
            partner_id=self._partner_id,   # pid present → must be rejected
        )
        headers = {"Authorization": f"Bearer {token}"}

        resp_users = client.post(
            "/v1/backoffice/users",
            json={"email": "x@x.com", "role": "viewer", "site_ids": [self._seed["site_id"]]},
            headers=headers,
        )
        assert resp_users.status_code == 403, (
            f"Expected 403 for partner admin on POST /users, got {resp_users.status_code}"
        )

        resp_partners = client.post(
            "/v1/backoffice/partners",
            json={"name": "Hack", "admin_email": "pa@h.com"},
            headers=headers,
        )
        assert resp_partners.status_code == 403, (
            f"Expected 403 for partner admin on POST /partners, got {resp_partners.status_code}"
        )

        resp_list = client.get("/v1/backoffice/users", headers=headers)
        assert resp_list.status_code == 403, (
            f"Expected 403 for partner admin on GET /users, got {resp_list.status_code}"
        )

    def test_gateway_token_rejected_on_backoffice(self) -> None:
        """A gateway JWT lacks 'tid' — must be rejected with 401 (not_a_user_token)."""
        resp = client.get("/v1/backoffice/users", headers=_gateway_headers())
        assert resp.status_code == 401, f"Expected 401 got {resp.status_code}: {resp.text}"
        assert resp.json()["detail"] == "not_a_user_token"
