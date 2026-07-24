"""Create agent_findings table — SDD §12.7 / §12.4 / §12.5.

agent_findings is the immutable audit trail of all AI-generated findings:
  - Stock audit results (task_type='stock_audit') written by the scheduled
    audit task (running as traxia_service)
  - Future Enjambre findings (Fase 4)

The SDD §12.7 "pattern of artifacts" requires findings to be:
  - Scoped strictly to the tenant/partner that owns the zone audited
  - Readable by the owning tenant admin, site operators, and the partner
    whose zones were audited
  - Writable by traxia_service (audit scheduler) and by traxia_app in
    partner context (Enjambre Fase 4 — SDD v3.3 fix for agent_findings_write)

Also adds ANTHROPIC_MODEL_COPILOT and ANTHROPIC_MODEL_AUDIT references
(stored in config.py, not in DB).
"""

revision = "0009"
down_revision = "0008"

from alembic import op


def upgrade():
    op.execute(
        """
        CREATE TABLE agent_findings (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            partner_id  UUID        REFERENCES partners(id) ON DELETE SET NULL,
            site_id     UUID        REFERENCES sites(id) ON DELETE SET NULL,
            zone_id     UUID        REFERENCES zones(id) ON DELETE SET NULL,
            task_type   TEXT        NOT NULL
                CHECK (task_type IN ('stock_audit', 'dwell_drop', 'copilot_audit')),
            summary     TEXT        NOT NULL,
            detail      JSONB       NOT NULL DEFAULT '{}',
            run_id      UUID        NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE agent_findings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agent_findings FORCE ROW LEVEL SECURITY")

    op.execute("CREATE INDEX idx_agent_findings_tenant ON agent_findings(tenant_id, created_at DESC)")
    op.execute("CREATE INDEX idx_agent_findings_zone ON agent_findings(zone_id, created_at DESC)")
    op.execute("CREATE INDEX idx_agent_findings_partner ON agent_findings(partner_id, created_at DESC)")

    op.execute("GRANT SELECT, INSERT ON agent_findings TO traxia_app")
    op.execute("GRANT SELECT, INSERT ON agent_findings TO traxia_service")

    # Tenant admin sees all findings for their tenant
    op.execute(
        """
        CREATE POLICY agent_findings_tenant_read
            ON agent_findings
            FOR SELECT
            TO traxia_app
            USING (
                tenant_id = app_current_tenant_id()
                AND app_current_partner_id() IS NULL
                AND app_current_role() IN ('admin', 'operator', 'viewer')
            )
        """
    )

    # Partner viewer sees only findings for their own partner
    op.execute(
        """
        CREATE POLICY agent_findings_partner_read
            ON agent_findings
            FOR SELECT
            TO traxia_app
            USING (
                tenant_id = app_current_tenant_id()
                AND partner_id = app_current_partner_id()
                AND app_current_partner_id() IS NOT NULL
            )
        """
    )

    # traxia_app can INSERT findings scoped to own tenant (partner agents, Fase 4)
    op.execute(
        """
        CREATE POLICY agent_findings_write
            ON agent_findings
            FOR INSERT
            TO traxia_app
            WITH CHECK (
                tenant_id = app_current_tenant_id()
                AND (
                    -- tenant admin/operator inserting tenant-level finding
                    (app_current_partner_id() IS NULL AND app_current_role() IN ('admin', 'operator'))
                    OR
                    -- partner agent inserting their own finding (SDD v3.3 fix)
                    (app_current_partner_id() IS NOT NULL AND partner_id = app_current_partner_id())
                )
            )
        """
    )

    # traxia_service: blanket access (audit scheduler, cross-tenant)
    op.execute(
        """
        CREATE POLICY agent_findings_service
            ON agent_findings
            FOR ALL
            TO traxia_service
            USING (true)
            WITH CHECK (true)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS agent_findings CASCADE")
