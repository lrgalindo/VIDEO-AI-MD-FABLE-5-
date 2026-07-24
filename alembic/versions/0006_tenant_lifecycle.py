"""Migration 0006 — Tenant lifecycle schema additions.

Changes:
  1. tenants.contact_email   — email submitted during self-registration
  2. tenants.approved_by     — platform_admin id that approved; NULL while onboarding
  3. tenants.approved_at     — approval timestamp
  4. tenants.deactivated_at  — soft-deactivation timestamp
  5. SuperAdmin RLS on tenants — traxia_service role can UPDATE tenant status
     (used by lifecycle endpoints; traxia_app keeps read-only tenant access)
  6. tenant_status = 'active' enforced in edge gateway activate & refresh:
     done in application code (auth/router.py), not as a DB policy, because
     the check requires a join across sites→tenants which is simpler in SQL
     within the UPDATE WHERE clause than as a separate policy.

Revision: 0006
Down revision: 0005
"""
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    # ── 1. Add lifecycle columns to tenants ──────────────────────────────────
    op.execute("""
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS contact_email   CITEXT,
    ADD COLUMN IF NOT EXISTS approved_by     UUID REFERENCES platform_admins(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approved_at     TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS deactivated_at  TIMESTAMPTZ;
""")

    # ── 2. traxia_service can UPDATE tenant status (lifecycle endpoints) ─────
    # traxia_service is the role used by service_conn() — lifecycle endpoints
    # run as service_conn (not traxia_app) because they affect cross-tenant
    # objects (platform-wide) without a per-tenant session GUC.
    op.execute("""
GRANT UPDATE (status, approved_by, approved_at, deactivated_at)
    ON tenants TO traxia_service;
GRANT INSERT ON tenants TO traxia_service;
GRANT SELECT ON tenants TO traxia_service;
GRANT SELECT ON platform_admins TO traxia_service;
""")

    # ── 3. RLS policy: traxia_service can INSERT new tenants (registration) ──
    op.execute("""
CREATE POLICY tenants_register ON tenants
    FOR INSERT TO traxia_service
    WITH CHECK (status = 'onboarding');

CREATE POLICY tenants_lifecycle ON tenants
    FOR UPDATE TO traxia_service
    USING (true)
    WITH CHECK (status IN ('active', 'inactive', 'onboarding'));

CREATE POLICY tenants_service_read ON tenants
    FOR SELECT TO traxia_service
    USING (true);
""")

    # ── 4. traxia_service can read edge_gateways + sites for deactivation ────
    op.execute("""
GRANT SELECT, UPDATE (status, refresh_token_hash, refresh_token_prev_hash,
                      refresh_token_expires_at, refresh_token_prev_expires_at)
    ON edge_gateways TO traxia_service;
GRANT SELECT ON sites TO traxia_service;
GRANT SELECT, UPDATE (status, activation_code_hash, activation_code_expires_at)
    ON edge_gateways TO traxia_service;
""")

    # ── 5. traxia_service can INSERT edge_gateways (created at approval) ─────
    op.execute("""
GRANT INSERT ON edge_gateways TO traxia_service;
""")


def downgrade() -> None:
    op.execute("""
DROP POLICY IF EXISTS tenants_register       ON tenants;
DROP POLICY IF EXISTS tenants_lifecycle      ON tenants;
DROP POLICY IF EXISTS tenants_service_read   ON tenants;

ALTER TABLE tenants
    DROP COLUMN IF EXISTS contact_email,
    DROP COLUMN IF EXISTS approved_by,
    DROP COLUMN IF EXISTS approved_at,
    DROP COLUMN IF EXISTS deactivated_at;

REVOKE UPDATE (status, approved_by, approved_at, deactivated_at)
    ON tenants FROM traxia_service;
REVOKE INSERT ON tenants FROM traxia_service;
REVOKE SELECT ON tenants FROM traxia_service;
REVOKE SELECT ON platform_admins FROM traxia_service;
REVOKE SELECT, UPDATE (status, refresh_token_hash, refresh_token_prev_hash,
                       refresh_token_expires_at, refresh_token_prev_expires_at)
    ON edge_gateways FROM traxia_service;
REVOKE SELECT ON sites FROM traxia_service;
REVOKE INSERT ON edge_gateways FROM traxia_service;
""")
