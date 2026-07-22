"""Tests for DELETE /v1/tenants/{tid}/partners/{pid}/data (SDD §12.12).

Critical assertions:
  1. Purge removes findings, users, zones attributed to the target partner.
  2. Purge does NOT touch Partner B data when purging Partner A (isolation).
  3. 403 if caller's tenant does not match URL tenant_id.
  4. 404 if partner does not exist or belongs to a different tenant.
"""

import json
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

client = TestClient(app, raise_server_exceptions=False)

_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/traxia",
)


@pytest.fixture
def db():
    conn = psycopg2.connect(_DB_URL)
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture
def tenant_setup(db):
    """One tenant with two partners, each with one zone and one agent_finding."""
    tid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    cam_id = str(uuid.uuid4())
    pa_id = str(uuid.uuid4())
    pb_id = str(uuid.uuid4())

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, name, vertical_type, status) "
            "VALUES (%s, 'ROF Tenant', 'retail', 'active')", (tid,)
        )
        cur.execute(
            "INSERT INTO sites (id, tenant_id, name, status) VALUES (%s, %s, 'ROF Site', 'active')",
            (sid, tid),
        )
        cur.execute(
            "INSERT INTO cameras (id, site_id, name, rtsp_url_ciphertext, rtsp_url_key_id, status) "
            "VALUES (%s, %s, 'ROF Cam', %s, 'test-key-v1', 'active')",
            (cam_id, sid, psycopg2.Binary(encrypt_test_rtsp())),
        )
        cur.execute(
            "INSERT INTO partners (id, tenant_id, name, status) VALUES (%s, %s, 'Partner A', 'active')",
            (pa_id, tid),
        )
        cur.execute(
            "INSERT INTO partners (id, tenant_id, name, status) VALUES (%s, %s, 'Partner B', 'active')",
            (pb_id, tid),
        )

        # Zone for Partner A
        za_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO zones (id, camera_id, owner_type, owner_partner_id, name, zone_type, coordinates) "
            "VALUES (%s, %s, 'PARTNER', %s, 'Zone A', 'shelf', '[[0,0],[1,0],[1,1],[0,1]]')",
            (za_id, cam_id, pa_id),
        )
        # Zone for Partner B
        zb_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO zones (id, camera_id, owner_type, owner_partner_id, name, zone_type, coordinates) "
            "VALUES (%s, %s, 'PARTNER', %s, 'Zone B', 'shelf', '[[0,0],[1,0],[1,1],[0,1]]')",
            (zb_id, cam_id, pb_id),
        )

        # Users for each partner
        ua_id = str(uuid.uuid4())
        ub_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO users (id, tenant_id, partner_id, email, role, status) "
            "VALUES (%s, %s, %s, %s, 'admin', 'active')",
            (ua_id, tid, pa_id, f"pa-{pa_id[:8]}@example.com"),
        )
        cur.execute(
            "INSERT INTO users (id, tenant_id, partner_id, email, role, status) "
            "VALUES (%s, %s, %s, %s, 'admin', 'active')",
            (ub_id, tid, pb_id, f"pb-{pb_id[:8]}@example.com"),
        )

        # agent_findings for Partner A and Partner B
        fa_id = str(uuid.uuid4())
        fb_id = str(uuid.uuid4())
        run_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO agent_findings (id, tenant_id, partner_id, site_id, zone_id, "
            "task_type, summary, detail, run_id) "
            "VALUES (%s, %s, %s, %s, %s, 'stock_audit', 'Finding A', '{}', %s)",
            (fa_id, tid, pa_id, sid, za_id, run_id),
        )
        cur.execute(
            "INSERT INTO agent_findings (id, tenant_id, partner_id, site_id, zone_id, "
            "task_type, summary, detail, run_id) "
            "VALUES (%s, %s, %s, %s, %s, 'stock_audit', 'Finding B', '{}', %s)",
            (fb_id, tid, pb_id, sid, zb_id, run_id),
        )
    db.commit()

    return {
        "tenant_id": tid, "site_id": sid, "cam_id": cam_id,
        "partner_a": pa_id, "partner_b": pb_id,
        "zone_a": za_id, "zone_b": zb_id,
        "user_a": ua_id, "user_b": ub_id,
        "finding_a": fa_id, "finding_b": fb_id,
    }


def _admin_token(tenant_id: str) -> str:
    return make_user_token(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        role="admin",
        site_ids=None,
        partner_id=None,
    )


# ── Positive: purge Partner A, verify isolation ───────────────────────────────

def test_purge_partner_a_removes_only_partner_a_data(tenant_setup, db):
    s = tenant_setup
    token = _admin_token(s["tenant_id"])

    resp = client.delete(
        f"/v1/tenants/{s['tenant_id']}/partners/{s['partner_a']}/data",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["purged"]["agent_findings"] == 1
    assert body["purged"]["users"] == 1
    assert body["purged"]["zones"] == 1

    with db.cursor() as cur:
        # Partner A data gone
        cur.execute("SELECT id FROM agent_findings WHERE id = %s", (s["finding_a"],))
        assert cur.fetchone() is None, "Finding A should be deleted"

        cur.execute("SELECT id FROM users WHERE id = %s", (s["user_a"],))
        assert cur.fetchone() is None, "User A should be deleted"

        cur.execute("SELECT id FROM zones WHERE id = %s", (s["zone_a"],))
        assert cur.fetchone() is None, "Zone A should be deleted"

        # Partner B data INTACT
        cur.execute("SELECT id FROM agent_findings WHERE id = %s", (s["finding_b"],))
        assert cur.fetchone() is not None, "Finding B must NOT be deleted"

        cur.execute("SELECT id FROM users WHERE id = %s", (s["user_b"],))
        assert cur.fetchone() is not None, "User B must NOT be deleted"

        cur.execute("SELECT id FROM zones WHERE id = %s", (s["zone_b"],))
        assert cur.fetchone() is not None, "Zone B must NOT be deleted"

        # Partner A row retained (audit trail), status changed
        cur.execute("SELECT status FROM partners WHERE id = %s", (s["partner_a"],))
        row = cur.fetchone()
        assert row is not None, "Partner A row must be retained for audit trail"
        assert row[0] == "inactive"


# ── Negative: authorization ───────────────────────────────────────────────────

def test_wrong_tenant_returns_403(tenant_setup):
    s = tenant_setup
    other_tenant = str(uuid.uuid4())
    token = _admin_token(other_tenant)

    resp = client.delete(
        f"/v1/tenants/{s['tenant_id']}/partners/{s['partner_a']}/data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_nonexistent_partner_returns_404(tenant_setup):
    s = tenant_setup
    token = _admin_token(s["tenant_id"])

    resp = client.delete(
        f"/v1/tenants/{s['tenant_id']}/partners/{uuid.uuid4()}/data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_partner_of_other_tenant_returns_404(tenant_setup, db):
    """A partner that exists but belongs to a different tenant → 404 (not 403 to avoid leakage)."""
    s = tenant_setup
    other_tenant_id = str(uuid.uuid4())
    other_partner_id = str(uuid.uuid4())

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (id, name, vertical_type, status) "
            "VALUES (%s, 'Other Tenant', 'retail', 'active')", (other_tenant_id,)
        )
        cur.execute(
            "INSERT INTO partners (id, tenant_id, name, status) VALUES (%s, %s, 'Other P', 'active')",
            (other_partner_id, other_tenant_id),
        )
    db.commit()

    token = _admin_token(s["tenant_id"])
    resp = client.delete(
        f"/v1/tenants/{s['tenant_id']}/partners/{other_partner_id}/data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
