"""Backoffice schema additions (Fase 2: users/partners/zones).

Changes:
- zones.zone_type: add CHECK constraint including 'staff_exclusion'
- users: add invite_token_hash + invite_expires_at for email invitation flow
- RLS: add users_update policy (admin can disable users) and usa_delete policy
- Views: add zone_dwell_summary excluding staff_exclusion zones from aggregates

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-20
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── zones.zone_type: enforce known values, add staff_exclusion ────────────
    # The initial schema had no CHECK constraint on zone_type (only a DEFAULT).
    # Adding it now. Existing rows must have zone_type in the allowed set.
    op.execute("""
ALTER TABLE zones
  ADD CONSTRAINT chk_zone_type
  CHECK (zone_type IN ('shelf','entrance','exit','checkout','staff_exclusion','generic'));
""")

    # ── users: invite token columns ───────────────────────────────────────────
    # Used by the one-step partner creation flow: a plaintext invite token is
    # returned to the caller; only its SHA-256 hash is stored here.
    op.execute("""
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS invite_token_hash   TEXT,
  ADD COLUMN IF NOT EXISTS invite_expires_at   TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_invite_token
  ON users(invite_token_hash) WHERE invite_token_hash IS NOT NULL;
""")

    # ── RLS: users_update — admin can change user status and clear invites ────
    op.execute("""
CREATE POLICY users_update ON users
  FOR UPDATE USING (
    app_current_role() = 'admin' AND (
      (app_current_partner_id() IS NULL AND users.tenant_id = app_current_tenant_id())
      OR (app_current_partner_id() IS NOT NULL AND users.partner_id = app_current_partner_id())
    )
  );
""")

    # ── RLS: usa_delete — admin can remove site assignments ───────────────────
    op.execute("""
CREATE POLICY usa_delete ON user_site_assignments
  FOR DELETE USING (
    app_current_partner_id() IS NULL AND app_current_role() = 'admin'
    AND sec_tenant_owns_site(user_site_assignments.site_id, app_current_tenant_id())
  );
""")

    # ── zone_dwell_summary view: excludes staff_exclusion zones ───────────────
    # Staff Exclusion zones are defined at the camera/zone level and represent
    # areas where only personnel are present.  Including them in customer-facing
    # dwell aggregates would inflate metrics; they are excluded here.
    op.execute("""
CREATE VIEW zone_dwell_summary
WITH (security_invoker = true) AS
SELECT
    z.id             AS zone_id,
    z.name           AS zone_name,
    z.zone_type,
    c.site_id,
    date_trunc('day', zds.entered_at)  AS day,
    count(*)                           AS sessions,
    round(avg(zds.dwell_seconds))      AS avg_dwell_seconds,
    max(zds.dwell_seconds)             AS max_dwell_seconds
FROM zone_dwell_sessions zds
JOIN zones z   ON z.id  = zds.zone_id
JOIN cameras c ON c.id  = z.camera_id
WHERE z.zone_type <> 'staff_exclusion'
GROUP BY z.id, z.name, z.zone_type, c.site_id,
         date_trunc('day', zds.entered_at);
""")

    # ── GRANT DELETE on user_site_assignments + SELECT on new view ───────────
    # DELETE was not included in the initial GRANT (migration 0001 only granted
    # SELECT/INSERT/UPDATE).  The usa_delete RLS policy above enforces the tenant
    # scoping constraint; we also need the object-level privilege.
    op.execute("GRANT DELETE ON user_site_assignments TO traxia_app;")
    op.execute("GRANT SELECT ON zone_dwell_summary TO traxia_app;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS zone_dwell_summary;")
    op.execute("DROP POLICY IF EXISTS usa_delete ON user_site_assignments;")
    op.execute("DROP POLICY IF EXISTS users_update ON users;")
    op.execute("DROP INDEX IF EXISTS idx_users_invite_token;")
    op.execute("""
ALTER TABLE users
  DROP COLUMN IF EXISTS invite_token_hash,
  DROP COLUMN IF EXISTS invite_expires_at;
""")
    op.execute("ALTER TABLE zones DROP CONSTRAINT IF EXISTS chk_zone_type;")
