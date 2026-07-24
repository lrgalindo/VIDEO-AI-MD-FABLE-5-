"""Motor de Acciones — SDD §12.10 (decisiones 3.1/7 y 3.1/8).

Tables:
  action_rules         — threshold / SOP compliance rule definitions (per tenant/site/zone)
  action_channels      — notification channel configs (Slack, Telegram, Email, WhatsApp)
  action_rule_channels — M:M binding rules to channels
  action_log           — immutable audit log of every dispatch attempt

All tables use FORCE ROW SECURITY with RLS policies scoped to
app_current_tenant_id() — same pattern as backoffice tables.
traxia_service gets blanket SELECT so the batch engine can scan all tenants.
"""

revision = "0008"
down_revision = "0007"

from alembic import op


def upgrade():
    op.execute(
        """
        CREATE TABLE action_rules (
            id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id                UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            site_id                  UUID        REFERENCES sites(id) ON DELETE CASCADE,
            zone_id                  UUID        REFERENCES zones(id) ON DELETE SET NULL,
            name                     TEXT        NOT NULL,
            description              TEXT,
            rule_type                TEXT        NOT NULL
                CHECK (rule_type IN (
                    'threshold',
                    'sop_staff_absent_checkout',
                    'sop_late_opening',
                    'sop_unattended_customer'
                )),
            threshold_value          INTEGER,    -- N people, or N minutes depending on rule_type
            threshold_window_minutes INTEGER,    -- observation window
            business_hours_start     TIME,       -- for SOP rules that check business hours
            business_hours_end       TIME,
            enabled                  BOOLEAN     NOT NULL DEFAULT TRUE,
            created_by               UUID,
            created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE action_rules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE action_rules FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE TABLE action_channels (
            id                               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id                        UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name                             TEXT        NOT NULL,
            channel_type                     TEXT        NOT NULL
                CHECK (channel_type IN ('slack', 'telegram', 'email', 'whatsapp')),
            config_json                      JSONB       NOT NULL DEFAULT '{}',
            enabled                          BOOLEAN     NOT NULL DEFAULT TRUE,
            whatsapp_cost_per_conversation_usd NUMERIC(10,4),  -- explicit, non-null only for whatsapp
            created_at                       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE action_channels ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE action_channels FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE TABLE action_rule_channels (
            rule_id    UUID NOT NULL REFERENCES action_rules(id) ON DELETE CASCADE,
            channel_id UUID NOT NULL REFERENCES action_channels(id) ON DELETE CASCADE,
            PRIMARY KEY (rule_id, channel_id)
        )
        """
    )
    op.execute("ALTER TABLE action_rule_channels ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE action_rule_channels FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE TABLE action_log (
            id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            rule_id         UUID        REFERENCES action_rules(id) ON DELETE SET NULL,
            tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            site_id         UUID        REFERENCES sites(id) ON DELETE SET NULL,
            triggered_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            channel_id      UUID        REFERENCES action_channels(id) ON DELETE SET NULL,
            status          TEXT        NOT NULL
                CHECK (status IN ('sent', 'failed', 'skipped')),
            payload_summary TEXT,
            meta_cost_usd   NUMERIC(10,4),   -- WhatsApp per-message Meta cost
            error_detail    TEXT
        )
        """
    )
    op.execute("ALTER TABLE action_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE action_log FORCE ROW LEVEL SECURITY")

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.execute("CREATE INDEX idx_action_rules_tenant ON action_rules(tenant_id)")
    op.execute("CREATE INDEX idx_action_rules_enabled ON action_rules(tenant_id) WHERE enabled = TRUE")
    op.execute("CREATE INDEX idx_action_log_tenant ON action_log(tenant_id, triggered_at DESC)")
    op.execute("CREATE INDEX idx_action_log_rule ON action_log(rule_id, triggered_at DESC)")

    # ── Grants ────────────────────────────────────────────────────────────────
    for tbl in ("action_rules", "action_channels", "action_rule_channels", "action_log"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO traxia_app")
        op.execute(f"GRANT SELECT, INSERT ON {tbl} TO traxia_service")

    # ── RLS policies — traxia_app (tenant-scoped) ─────────────────────────────

    # action_rules
    op.execute(
        """
        CREATE POLICY action_rules_admin
            ON action_rules
            FOR ALL
            TO traxia_app
            USING (
                tenant_id = app_current_tenant_id()
                AND app_current_role() = 'admin'
            )
            WITH CHECK (
                tenant_id = app_current_tenant_id()
                AND app_current_role() = 'admin'
            )
        """
    )
    op.execute(
        """
        CREATE POLICY action_rules_read
            ON action_rules
            FOR SELECT
            TO traxia_app
            USING (
                tenant_id = app_current_tenant_id()
                AND app_current_role() IN ('admin', 'operator', 'viewer')
            )
        """
    )

    # action_channels
    op.execute(
        """
        CREATE POLICY action_channels_admin
            ON action_channels
            FOR ALL
            TO traxia_app
            USING (
                tenant_id = app_current_tenant_id()
                AND app_current_role() = 'admin'
            )
            WITH CHECK (
                tenant_id = app_current_tenant_id()
                AND app_current_role() = 'admin'
            )
        """
    )
    op.execute(
        """
        CREATE POLICY action_channels_read
            ON action_channels
            FOR SELECT
            TO traxia_app
            USING (
                tenant_id = app_current_tenant_id()
                AND app_current_role() IN ('admin', 'operator', 'viewer')
            )
        """
    )

    # action_rule_channels — access via JOIN to action_rules (tenant-scoped)
    op.execute(
        """
        CREATE POLICY action_rule_channels_policy
            ON action_rule_channels
            FOR ALL
            TO traxia_app
            USING (
                EXISTS (
                    SELECT 1 FROM action_rules ar
                    WHERE ar.id = action_rule_channels.rule_id
                      AND ar.tenant_id = app_current_tenant_id()
                      AND app_current_role() = 'admin'
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM action_rules ar
                    WHERE ar.id = action_rule_channels.rule_id
                      AND ar.tenant_id = app_current_tenant_id()
                      AND app_current_role() = 'admin'
                )
            )
        """
    )
    op.execute(
        """
        CREATE POLICY action_rule_channels_read
            ON action_rule_channels
            FOR SELECT
            TO traxia_app
            USING (
                EXISTS (
                    SELECT 1 FROM action_rules ar
                    WHERE ar.id = action_rule_channels.rule_id
                      AND ar.tenant_id = app_current_tenant_id()
                )
            )
        """
    )

    # action_log — read for admin/operator; INSERT only for traxia_service
    op.execute(
        """
        CREATE POLICY action_log_read
            ON action_log
            FOR SELECT
            TO traxia_app
            USING (
                tenant_id = app_current_tenant_id()
                AND app_current_role() IN ('admin', 'operator', 'viewer')
            )
        """
    )

    # ── RLS policies — traxia_service (cross-tenant scan for batch engine) ───
    for tbl in ("action_rules", "action_channels", "action_rule_channels", "action_log"):
        op.execute(
            f"""
            CREATE POLICY {tbl}_service
                ON {tbl}
                FOR ALL
                TO traxia_service
                USING (true)
                WITH CHECK (true)
            """
        )


def downgrade():
    for tbl in ("action_log", "action_rule_channels", "action_channels", "action_rules"):
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
