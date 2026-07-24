"""Grant traxia_service INSERT/UPDATE on sites + add unrestricted RLS policy.

The lifecycle endpoints (approve, deactivate) run as traxia_service and need:
  - INSERT on sites (approve creates a bootstrap site)
  - SELECT on sites unrestricted (deactivate JOINs sites to find tenant's gateways)
  - UPDATE on sites is added for completeness (status changes on deactivation path)

The existing sites_read and sites_provision RLS policies use traxia_app GUCs
(app_current_role, app_provision_tenant_id) which are never set for traxia_service
connections — making all site rows invisible.  A new sites_service policy gives
traxia_service unconditional access, matching the same blanket-trust pattern
already used for edge_gateways (edge_gateways_service_read/write/update).
"""

revision = "0007"
down_revision = "0006"

from alembic import op


def upgrade():
    op.execute("GRANT SELECT, INSERT, UPDATE ON sites TO traxia_service")

    # Blanket RLS policy for traxia_service — mirrors edge_gateways pattern.
    # traxia_service is a trusted backend role; no tenant-scoping needed.
    op.execute(
        """
        CREATE POLICY sites_service
            ON sites
            FOR ALL
            TO traxia_service
            USING (true)
            WITH CHECK (true)
        """
    )


def downgrade():
    op.execute("DROP POLICY IF EXISTS sites_service ON sites")
    op.execute("REVOKE INSERT, UPDATE ON sites FROM traxia_service")
