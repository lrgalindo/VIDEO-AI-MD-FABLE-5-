"""HTTP-layer + isolation tests for GET /v1/findings (SDD §12.5 / Fase 3).

Tests use FastAPI TestClient + real PostgreSQL (committed fixtures, rolled back
in teardown).  No mocking of the DB layer — RLS is what we are testing.

Running:
    JWT_SECRET=test-secret \\
    DATABASE_URL=postgresql://rodrigogalindo@localhost:5432/traxia \\
    pytest tests/findings/test_findings_api.py -v

Critical negative test: partner isolation.
Two Partners (P and Q) are seeded within the same Tenant.  Each owns a
distinct zone, and each has a distinct agent_findings row.  The test verifies
that Partner P cannot see Partner Q's finding and vice versa.

This is the same pattern as the prompt-injection tests in test_copilot_api.py,
applied to the findings endpoint.  A test that only confirms "partner sees their
own finding" (positive path) is insufficient — it does not distinguish a correct
RLS policy from a broken one that returns everything.
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

_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://rodrigogalindo@localhost:5432/traxia",
)

client = TestClient(app, raise_server_exceptions=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uid() -> str:
    return str(uuid.uuid4())


def _admin_token(tenant_id: str, user_id: str) -> str:
    return make_user_token(user_id, tenant_id, "admin")


def _partner_token(tenant_id: str, user_id: str, partner_id: str) -> str:
    return make_user_token(user_id, tenant_id, "viewer", partner_id=partner_id)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db() -> Generator[psycopg2.extras.RealDictCursor, None, None]:
    conn = psycopg2.connect(_DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    yield conn.cursor()
    conn.rollback()
    conn.close()


@pytest.fixture(scope="module")
def seed(db: psycopg2.extras.RealDictCursor):
    """
    Tenant A
      ├─ Site A
      │    ├─ Camera A
      │    │    ├─ Zone P  → owner_type=PARTNER, owner_partner_id=Partner P
      │    │    └─ Zone Q  → owner_type=PARTNER, owner_partner_id=Partner Q
      │    └─ (Camera A is shared between both zones for simplicity)
      ├─ Partner P (user: User P — partner viewer)
      ├─ Partner Q (user: User Q — partner viewer)
      └─ User Admin (admin)

    Findings:
      Finding FP → zone_id=Zone P, partner_id=Partner P, tenant_id=Tenant A
      Finding FQ → zone_id=Zone Q, partner_id=Partner Q, tenant_id=Tenant A

    Expected isolation:
      Partner P: sees FP, does NOT see FQ
      Partner Q: sees FQ, does NOT see FP
      Tenant Admin: sees both FP and FQ
      Tenant B admin: sees neither (cross-tenant isolation)
    """
    tenant_a_id = _uid()
    tenant_b_id = _uid()
    site_a_id = _uid()
    site_b_id = _uid()
    cam_a_id = _uid()
    cam_b_id = _uid()
    zone_p_id = _uid()
    zone_q_id = _uid()
    partner_p_id = _uid()
    partner_q_id = _uid()
    user_admin_id = _uid()
    user_p_id = _uid()
    user_q_id = _uid()
    user_b_admin_id = _uid()
    finding_p_id = _uid()
    finding_q_id = _uid()
    run_id = _uid()

    # Tenants
    for tid, name in [(tenant_a_id, "FND Tenant A"), (tenant_b_id, "FND Tenant B")]:
        db.execute(
            "INSERT INTO tenants (id, name, vertical_type, status, contact_email) "
            "VALUES (%s, %s, 'retail', 'active', %s)",
            (tid, name, f"{name.lower().replace(' ', '')}@test.com"),
        )

    # Sites
    for sid, tid in [(site_a_id, tenant_a_id), (site_b_id, tenant_b_id)]:
        db.execute(
            "INSERT INTO sites (id, tenant_id, name, status) VALUES (%s, %s, 'Site', 'active')",
            (sid, tid),
        )

    # Cameras
    for cid, sid in [(cam_a_id, site_a_id), (cam_b_id, site_b_id)]:
        db.execute(
            "INSERT INTO cameras (id, site_id, name, rtsp_url_ciphertext, rtsp_url_key_id, status) "
            "VALUES (%s, %s, 'Cam', %s, 'test-key-v1', 'active')",
            (cid, sid, psycopg2.Binary(encrypt_test_rtsp())),
        )

    # Partners
    for pid, name in [(partner_p_id, "Partner P"), (partner_q_id, "Partner Q")]:
        db.execute(
            "INSERT INTO partners (id, tenant_id, name, status) VALUES (%s, %s, %s, 'active')",
            (pid, tenant_a_id, name),
        )

    # Zones — each owned by a different partner
    db.execute(
        "INSERT INTO zones (id, camera_id, name, zone_type, coordinates, "
        "owner_type, owner_partner_id) "
        "VALUES (%s, %s, 'Zone P', 'shelf', '[[0,0],[1,0],[1,1],[0,1]]', 'PARTNER', %s)",
        (zone_p_id, cam_a_id, partner_p_id),
    )
    db.execute(
        "INSERT INTO zones (id, camera_id, name, zone_type, coordinates, "
        "owner_type, owner_partner_id) "
        "VALUES (%s, %s, 'Zone Q', 'shelf', '[[0,0],[1,0],[1,1],[0,1]]', 'PARTNER', %s)",
        (zone_q_id, cam_a_id, partner_q_id),
    )

    # Users
    db.execute(
        "INSERT INTO users (id, tenant_id, email, role, status) "
        "VALUES (%s, %s, 'admin-fnd@a.com', 'admin', 'active')",
        (user_admin_id, tenant_a_id),
    )
    db.execute(
        "INSERT INTO users (id, tenant_id, partner_id, email, role, status) "
        "VALUES (%s, %s, %s, 'partner-p@a.com', 'viewer', 'active')",
        (user_p_id, tenant_a_id, partner_p_id),
    )
    db.execute(
        "INSERT INTO users (id, tenant_id, partner_id, email, role, status) "
        "VALUES (%s, %s, %s, 'partner-q@a.com', 'viewer', 'active')",
        (user_q_id, tenant_a_id, partner_q_id),
    )
    db.execute(
        "INSERT INTO users (id, tenant_id, email, role, status) "
        "VALUES (%s, %s, 'admin-fnd@b.com', 'admin', 'active')",
        (user_b_admin_id, tenant_b_id),
    )

    # Findings — seeded directly (bypassing audit cycle) to avoid requiring ANTHROPIC_API_KEY
    detail_p = json.dumps({
        "recent_avg_dwell": 15,
        "baseline_avg_dwell": 90,
        "vision_finding": "Shelves partially empty near aisle 2.",
        "snapshot_available": True,
        "snapshot_r2_key": f"snapshots/{zone_p_id}/{run_id}.jpg",
    })
    detail_q = json.dumps({
        "recent_avg_dwell": 20,
        "baseline_avg_dwell": 110,
        "vision_finding": "Product misplaced in Zone Q.",
        "snapshot_available": True,
        "snapshot_r2_key": f"snapshots/{zone_q_id}/{run_id}.jpg",
    })
    db.execute(
        "INSERT INTO agent_findings (id, tenant_id, partner_id, site_id, zone_id, "
        "task_type, summary, detail, run_id) "
        "VALUES (%s, %s, %s, %s, %s, 'stock_audit', %s, %s::jsonb, %s)",
        (finding_p_id, tenant_a_id, partner_p_id, site_a_id, zone_p_id,
         "Zone P: Shelves partially empty.", detail_p, run_id),
    )
    db.execute(
        "INSERT INTO agent_findings (id, tenant_id, partner_id, site_id, zone_id, "
        "task_type, summary, detail, run_id) "
        "VALUES (%s, %s, %s, %s, %s, 'stock_audit', %s, %s::jsonb, %s)",
        (finding_q_id, tenant_a_id, partner_q_id, site_a_id, zone_q_id,
         "Zone Q: Product misplaced.", detail_q, run_id),
    )
    db.connection.commit()

    data = {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "partner_p_id": partner_p_id,
        "partner_q_id": partner_q_id,
        "user_admin_id": user_admin_id,
        "user_p_id": user_p_id,
        "user_q_id": user_q_id,
        "user_b_admin_id": user_b_admin_id,
        "finding_p_id": finding_p_id,
        "finding_q_id": finding_q_id,
        "zone_p_id": zone_p_id,
        "zone_q_id": zone_q_id,
        "site_a_id": site_a_id,
    }
    yield data

    # Teardown — most specific first (FK order)
    db.execute(
        "DELETE FROM agent_findings WHERE id IN (%s, %s)",
        (finding_p_id, finding_q_id),
    )
    db.execute(
        "DELETE FROM zones WHERE id IN (%s, %s)",
        (zone_p_id, zone_q_id),
    )
    db.execute(
        "DELETE FROM cameras WHERE id IN (%s, %s)",
        (cam_a_id, cam_b_id),
    )
    db.execute(
        "DELETE FROM users WHERE id IN (%s, %s, %s, %s)",
        (user_admin_id, user_p_id, user_q_id, user_b_admin_id),
    )
    db.execute(
        "DELETE FROM partners WHERE id IN (%s, %s)",
        (partner_p_id, partner_q_id),
    )
    db.execute(
        "DELETE FROM sites WHERE id IN (%s, %s)",
        (site_a_id, site_b_id),
    )
    db.execute(
        "DELETE FROM tenants WHERE id IN (%s, %s)",
        (tenant_a_id, tenant_b_id),
    )
    db.connection.commit()


# ── Tests: basic access ───────────────────────────────────────────────────────

class TestFindingsAccess:
    def test_unauthenticated_returns_401_or_403(self, seed):
        resp = client.get("/v1/findings")
        assert resp.status_code in (401, 403)

    def test_admin_can_list_findings(self, seed):
        """Tenant admin sees findings for their tenant (positive path)."""
        token = _admin_token(seed["tenant_a_id"], seed["user_admin_id"])
        resp = client.get("/v1/findings", headers=_auth(token))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert seed["finding_p_id"] in ids
        assert seed["finding_q_id"] in ids

    def test_partner_p_sees_own_finding(self, seed):
        """Partner P can see their own finding (positive path — baseline)."""
        token = _partner_token(
            seed["tenant_a_id"], seed["user_p_id"], seed["partner_p_id"]
        )
        resp = client.get("/v1/findings", headers=_auth(token))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert seed["finding_p_id"] in ids, "Partner P must see their own finding"


# ── Tests: negative isolation (the critical tests) ────────────────────────────

class TestFindingsIsolation:
    """
    These tests verify that RLS on agent_findings enforces partner-level isolation.

    The seed contains two findings in the same tenant (FP for Partner P, FQ for
    Partner Q).  A positive-only test ("Partner P sees FP") does not distinguish
    a correct policy from a broken one that returns all findings for the tenant.

    The negative test forces this distinction: Partner P must NOT see FQ, and
    Partner Q must NOT see FP.  Only the tenant admin sees both.
    """

    def test_partner_p_cannot_see_partner_q_finding(self, seed):
        """CRITICAL: Partner P must not see the finding belonging to Partner Q's zone."""
        token = _partner_token(
            seed["tenant_a_id"], seed["user_p_id"], seed["partner_p_id"]
        )
        resp = client.get("/v1/findings", headers=_auth(token))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert seed["finding_q_id"] not in ids, (
            f"RLS FAILURE: Partner P can see Partner Q's finding {seed['finding_q_id']}. "
            "agent_findings RLS policy for partner_viewer must filter by partner_id."
        )

    def test_partner_q_cannot_see_partner_p_finding(self, seed):
        """CRITICAL: Partner Q must not see the finding belonging to Partner P's zone."""
        token = _partner_token(
            seed["tenant_a_id"], seed["user_q_id"], seed["partner_q_id"]
        )
        resp = client.get("/v1/findings", headers=_auth(token))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert seed["finding_p_id"] not in ids, (
            f"RLS FAILURE: Partner Q can see Partner P's finding {seed['finding_p_id']}. "
            "agent_findings RLS policy for partner_viewer must filter by partner_id."
        )

    def test_tenant_b_admin_cannot_see_tenant_a_findings(self, seed):
        """Cross-tenant isolation: Tenant B admin sees zero findings (both are in Tenant A)."""
        token = _admin_token(seed["tenant_b_id"], seed["user_b_admin_id"])
        resp = client.get("/v1/findings", headers=_auth(token))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert seed["finding_p_id"] not in ids, "Cross-tenant leak: Tenant B sees Tenant A finding FP"
        assert seed["finding_q_id"] not in ids, "Cross-tenant leak: Tenant B sees Tenant A finding FQ"

    def test_partner_p_result_contains_no_other_tenant_data(self, seed):
        """Every finding returned to Partner P must belong to their tenant and zone."""
        token = _partner_token(
            seed["tenant_a_id"], seed["user_p_id"], seed["partner_p_id"]
        )
        resp = client.get("/v1/findings", headers=_auth(token))
        assert resp.status_code == 200
        for finding in resp.json():
            # Every finding must be for Zone P (the only zone Partner P owns)
            assert finding["zone_id"] == seed["zone_p_id"], (
                f"Partner P received finding for unexpected zone {finding['zone_id']}"
            )


# ── Tests: snapshot_url is never the raw R2 key ───────────────────────────────

class TestFindingsSnapshotUrl:
    """
    Verify the response contract for snapshot_url.

    The R2 object key (snapshots/{zone_id}/{run_id}.jpg) is an internal
    storage reference that must never be sent to the client.  The finding
    detail stored in the DB contains snapshot_r2_key, which the endpoint
    strips and replaces with a presigned URL (or None if R2 is unconfigured).
    """

    def test_snapshot_r2_key_not_exposed_in_response(self, seed):
        """The raw R2 key must never appear in the API response body."""
        token = _partner_token(
            seed["tenant_a_id"], seed["user_p_id"], seed["partner_p_id"]
        )
        resp = client.get("/v1/findings", headers=_auth(token))
        assert resp.status_code == 200
        response_text = resp.text
        # The raw R2 key contains the zone_id and run_id — neither should appear
        # in the response JSON directly (only through snapshot_url if R2 is configured)
        assert "snapshot_r2_key" not in response_text, (
            "The internal R2 key field was exposed in the API response. "
            "Only snapshot_url (presigned URL or None) must be returned."
        )

    def test_snapshot_url_is_none_when_r2_unconfigured(self, seed):
        """Without R2 credentials, snapshot_url must be null (not an error)."""
        # In the test environment R2 credentials are not set, so snapshot_url = None
        token = _partner_token(
            seed["tenant_a_id"], seed["user_p_id"], seed["partner_p_id"]
        )
        resp = client.get("/v1/findings", headers=_auth(token))
        assert resp.status_code == 200
        for finding in resp.json():
            # snapshot_available is True in the seed detail (vision was run),
            # but snapshot_url must be None because R2 is not configured in tests
            assert finding.get("snapshot_url") is None, (
                "Expected snapshot_url=null when R2 credentials are not set. "
                "If R2 env vars are set in this test run, this assertion should be removed."
            )
