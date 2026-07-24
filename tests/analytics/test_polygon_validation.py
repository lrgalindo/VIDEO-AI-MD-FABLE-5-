"""
Tests for polygon geometry validation in POST /v1/zones.

Unit-tests the pure-Python helpers directly (no HTTP server needed),
plus integration-style tests against the FastAPI endpoint using httpx.

Bowtie ("moño") reference shape — 4 vertices that force a self-intersection:

    (0,100) -------- (100,100)
         \\          /
          \\        /
           X      X      ← edges cross here at (50,50)
          /        \\
         /          \\
    (0,0) ---------- (100,0)

Vertex order: [(0,0), (100,100), (100,0), (0,100)]
  edge 0: (0,0)   → (100,100)
  edge 1: (100,100) → (100,0)
  edge 2: (100,0)  → (0,100)
  edge 3: (0,100)  → (0,0)
Non-adjacent pair (0, 2): edges 0 and 2 cross at (50,50) → self-intersecting.
"""
import pytest

from cloud.analytics.geometry import _ccw, segments_cross, polygon_self_intersects

# Aliases so test bodies read the same as before
_segments_cross = segments_cross
_polygon_self_intersects = polygon_self_intersects


# ── Unit tests: _ccw ──────────────────────────────────────────────────────────

class TestCCW:
    def test_counter_clockwise(self):
        # A=(0,0), B=(1,0), C=(0,1) — CCW turn
        assert _ccw(0, 0, 1, 0, 0, 1) is True

    def test_clockwise(self):
        # A=(0,0), B=(0,1), C=(1,0) — CW turn
        assert _ccw(0, 0, 0, 1, 1, 0) is False

    def test_collinear(self):
        # A=(0,0), B=(1,0), C=(2,0) — collinear, not strictly CCW
        assert _ccw(0, 0, 1, 0, 2, 0) is False


# ── Unit tests: _segments_cross ───────────────────────────────────────────────

class TestSegmentsCross:
    def test_crossing_diagonals(self):
        # Classic X: (0,0)-(100,100) and (100,0)-(0,100) cross at (50,50)
        assert _segments_cross([0, 0], [100, 100], [100, 0], [0, 100]) is True

    def test_parallel_horizontal(self):
        assert _segments_cross([0, 0], [100, 0], [0, 10], [100, 10]) is False

    def test_t_intersection_touching_endpoint(self):
        # Segments that touch at one endpoint — should NOT count as crossing
        # because adjacent polygon edges share a vertex and must be ignored
        assert _segments_cross([0, 0], [50, 50], [50, 50], [100, 0]) is False

    def test_perpendicular_non_overlapping(self):
        # Perpendicular but the actual segments don't reach the crossing point
        assert _segments_cross([0, 0], [10, 0], [20, -5], [20, 5]) is False

    def test_perpendicular_overlapping(self):
        # A horizontal and a vertical that genuinely cross
        assert _segments_cross([0, 5], [10, 5], [5, 0], [5, 10]) is True


# ── Unit tests: _polygon_self_intersects ─────────────────────────────────────

class TestPolygonSelfIntersects:
    def test_bowtie_4_vertices(self):
        # THE canonical bowtie: (0,0), (100,100), (100,0), (0,100)
        bowtie = [[0, 0], [100, 100], [100, 0], [0, 100]]
        assert _polygon_self_intersects(bowtie) is True

    def test_simple_square(self):
        square = [[0, 0], [100, 0], [100, 100], [0, 100]]
        assert _polygon_self_intersects(square) is False

    def test_convex_pentagon(self):
        import math
        pts = [[int(50 * math.cos(2 * math.pi * i / 5)),
                int(50 * math.sin(2 * math.pi * i / 5))] for i in range(5)]
        assert _polygon_self_intersects(pts) is False

    def test_triangle_cannot_self_intersect(self):
        # Triangles have no non-adjacent edge pairs → always False
        triangle = [[0, 0], [100, 0], [50, 80]]
        assert _polygon_self_intersects(triangle) is False

    def test_star_shape_self_intersects(self):
        # A 5-point star drawn as a single path self-intersects
        star = [
            [50, 0], [21, 90], [98, 35], [2, 35], [79, 90]
        ]
        assert _polygon_self_intersects(star) is True

    def test_l_shape_concave_no_intersection(self):
        # Concave L-shape — no self-intersection
        l_shape = [[0, 0], [60, 0], [60, 30], [30, 30], [30, 60], [0, 60]]
        assert _polygon_self_intersects(l_shape) is False

    def test_figure_eight_self_intersects(self):
        # A figure-8 with 6 vertices
        figure8 = [[0, 0], [50, 50], [100, 0], [100, 100], [50, 50], [0, 100]]
        assert _polygon_self_intersects(figure8) is True


# ── Integration tests: POST /v1/zones endpoint ────────────────────────────────

try:
    import httpx
    from fastapi.testclient import TestClient
    from cloud.main import app
    from cloud.auth.tokens import make_user_token
    import os, uuid

    _HAS_SERVER = True
except Exception:
    _HAS_SERVER = False


@pytest.mark.skipif(not _HAS_SERVER, reason="server deps not available")
class TestZoneEndpointPolygonValidation:
    """Requires DATABASE_URL and JWT_SECRET env vars (same as other API tests)."""

    @pytest.fixture
    def client(self):
        # raise_server_exceptions=False: server-side exceptions return HTTP 500
        # instead of propagating into the test, so we can assert on status codes.
        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture
    def admin_headers(self):
        token = make_user_token(
            user_id=str(uuid.uuid4()),
            tenant_id="bb100000-0000-4000-8000-000000000001",
            role="admin",
        )
        return {"Authorization": f"Bearer {token}"}

    def _zone_body(self, points: list) -> dict:
        return {
            "camera_id": "bb100000-0000-4000-8000-000000000004",
            "name": "Test Zone",
            "zone_type": "shelf",
            "coordinates": {"type": "polygon", "points": points},
        }

    def test_valid_square_accepted(self, client, admin_headers):
        body = self._zone_body([[0, 0], [100, 0], [100, 100], [0, 100]])
        r = client.post("/v1/zones", json=body, headers=admin_headers)
        # 201 or 403/500 depending on DB state — the key is it's NOT 422
        assert r.status_code != 422, r.json()

    def test_bowtie_rejected_with_422(self, client, admin_headers):
        # (0,0)→(100,100)→(100,0)→(0,100): edge 0 and edge 2 cross at (50,50)
        body = self._zone_body([[0, 0], [100, 100], [100, 0], [0, 100]])
        r = client.post("/v1/zones", json=body, headers=admin_headers)
        assert r.status_code == 422
        assert "self-intersecting" in r.json()["detail"]

    def test_fewer_than_3_vertices_rejected(self, client, admin_headers):
        body = self._zone_body([[0, 0], [100, 0]])
        r = client.post("/v1/zones", json=body, headers=admin_headers)
        assert r.status_code == 422
        assert "3 vertices" in r.json()["detail"]

    def test_star_polygon_rejected(self, client, admin_headers):
        star = [[50, 0], [21, 90], [98, 35], [2, 35], [79, 90]]
        body = self._zone_body(star)
        r = client.post("/v1/zones", json=body, headers=admin_headers)
        assert r.status_code == 422
        assert "self-intersecting" in r.json()["detail"]
