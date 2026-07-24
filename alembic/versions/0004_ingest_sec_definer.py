"""SECURITY DEFINER helper for tracking_coordinates ingest (§8.6).

The tracking_coordinates_ingest policy references cameras to verify site ownership.
Cameras is also FORCE ROW LEVEL SECURITY, and its read policy requires user-facing
GUCs (tenant_id, role) that are not set during telemetry ingest — only
app.current_ingest_site_id is available from the JWT.

Fix: replace the inline EXISTS(cameras) with a SECURITY DEFINER function that
bypasses cameras RLS.  The function still enforces the correct constraint (camera
must belong to the site from the JWT), but without requiring cameras to be visible
to the executing role.

Also GRANTs traxia_app INSERT on tracking_coordinates and EXECUTE on the new
function so the ingest endpoint (which switches to traxia_app) can run it.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-20
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
-- Used by: tracking_coordinates_ingest (FOR INSERT WITH CHECK).
--
-- Recursion cycle broken:
--   tracking_coordinates_ingest calls  EXISTS(SELECT FROM cameras)
--   → cameras has FORCE ROW LEVEL SECURITY
--   → cameras_read policy requires app.current_tenant_id + app.current_actor_role
--   → those GUCs are NOT set during telemetry ingest (only app.current_ingest_site_id
--     is available from the JWT's "sid" claim)
--   → cameras returns an empty set to traxia_app → every INSERT is blocked.
--
-- This SECURITY DEFINER function runs as the function owner (postgres), which
-- bypasses cameras RLS entirely.  It enforces the correct invariant directly:
-- the camera must exist AND belong to the site supplied by the ingest JWT,
-- without ever requiring user-facing session GUCs.
CREATE OR REPLACE FUNCTION sec_camera_on_ingest_site(p_cam UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM cameras c
    WHERE c.id = p_cam AND c.site_id = app_current_ingest_site_id()
  )
$$;

GRANT EXECUTE ON FUNCTION sec_camera_on_ingest_site(uuid) TO traxia_app;

DROP POLICY IF EXISTS tracking_coordinates_ingest ON tracking_coordinates;
CREATE POLICY tracking_coordinates_ingest ON tracking_coordinates
  FOR INSERT WITH CHECK (sec_camera_on_ingest_site(tracking_coordinates.camera_id));
""")


def downgrade() -> None:
    op.execute("""
DROP POLICY IF EXISTS tracking_coordinates_ingest ON tracking_coordinates;
CREATE POLICY tracking_coordinates_ingest ON tracking_coordinates
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM cameras c
      WHERE c.id = tracking_coordinates.camera_id
        AND c.site_id = app_current_ingest_site_id()
    )
  );
DROP FUNCTION IF EXISTS sec_camera_on_ingest_site(uuid);
""")
