"""Initial schema: extensions, tables, RLS, pg_partman (SDD v3.4-FINAL)

Revision ID: 0001
Revises:
Create Date: 2026-07-20
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")
    op.execute("CREATE SCHEMA IF NOT EXISTS partman;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;")

    # ── Session-GUC helpers (LEAKPROOF — superuser required; fine in Docker) ─
    op.execute("""
CREATE OR REPLACE FUNCTION app_current_tenant_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
$$;

CREATE OR REPLACE FUNCTION app_current_partner_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_partner_id', true), '')::UUID
$$;

CREATE OR REPLACE FUNCTION app_current_role() RETURNS TEXT
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_actor_role', true), '')
$$;

CREATE OR REPLACE FUNCTION app_current_site_ids() RETURNS UUID[]
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT CASE
    WHEN NULLIF(current_setting('app.current_user_site_ids', true), '') IS NULL
    THEN ARRAY[]::UUID[]
    ELSE string_to_array(current_setting('app.current_user_site_ids', true), ',')::UUID[]
  END
$$;

CREATE OR REPLACE FUNCTION app_current_reseller_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_reseller_id', true), '')::UUID
$$;

CREATE OR REPLACE FUNCTION app_current_user_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_user_id', true), '')::UUID
$$;

CREATE OR REPLACE FUNCTION app_provision_tenant_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.provision_tenant_id', true), '')::UUID
$$;

CREATE OR REPLACE FUNCTION app_current_ingest_site_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_ingest_site_id', true), '')::UUID
$$;

CREATE OR REPLACE FUNCTION app_motor_site_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.motor_site_id', true), '')::UUID
$$;
""")

    # ── Core tables (dependency order) ────────────────────────────────────────
    op.execute("""
-- Section 3.1 decision 2: resellers schema + RLS only, no UI/backend (deferred v2.0)
CREATE TABLE resellers (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tenants (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reseller_id   UUID NULL REFERENCES resellers(id) ON DELETE SET NULL,
    name          TEXT NOT NULL,
    vertical_type TEXT NOT NULL CHECK (vertical_type IN ('retail','banking','logistics')),
    status        TEXT NOT NULL DEFAULT 'onboarding' CHECK (status IN ('active','inactive','onboarding')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tenants_reseller_id ON tenants(reseller_id);

-- Section 3.1 decision 3/2.2: access_expires_at + partial index
CREATE TABLE partners (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
    access_expires_at TIMESTAMPTZ NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_partners_tenant_id ON partners(tenant_id);
CREATE INDEX idx_partners_access_expiry ON partners(access_expires_at)
  WHERE status = 'active' AND access_expires_at IS NOT NULL;

CREATE TABLE sites (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    address    TEXT,
    timezone   TEXT NOT NULL DEFAULT 'America/Guatemala',
    status     TEXT NOT NULL DEFAULT 'onboarding' CHECK (status IN ('active','inactive','onboarding')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sites_tenant_id ON sites(tenant_id);

CREATE TABLE cameras (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id             UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    rtsp_url_ciphertext BYTEA NOT NULL,
    rtsp_url_key_id     TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cameras_site_id ON cameras(site_id);

-- Section 8.0: owner_tenant_id / owner_partner_id exclusive via CHECK
CREATE TABLE zones (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id        UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    owner_type       TEXT NOT NULL CHECK (owner_type IN ('TENANT','PARTNER')),
    owner_tenant_id  UUID NULL REFERENCES tenants(id) ON DELETE CASCADE,
    owner_partner_id UUID NULL REFERENCES partners(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    zone_type        TEXT NOT NULL DEFAULT 'shelf',
    coordinates      JSONB NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_zone_owner_exclusive CHECK (
        (owner_type = 'TENANT'  AND owner_tenant_id  IS NOT NULL AND owner_partner_id IS NULL) OR
        (owner_type = 'PARTNER' AND owner_partner_id IS NOT NULL AND owner_tenant_id  IS NULL)
    )
);
CREATE INDEX idx_zones_camera_id    ON zones(camera_id);
CREATE INDEX idx_zones_owner_tenant  ON zones(owner_tenant_id);
CREATE INDEX idx_zones_owner_partner ON zones(owner_partner_id);

-- Section 8.6: native RANGE partitioning + pg_partman (no TimescaleDB)
CREATE TABLE tracking_coordinates (
    "time"    TIMESTAMPTZ NOT NULL,
    camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    person_id TEXT NOT NULL,
    x         INTEGER NOT NULL,
    y         INTEGER NOT NULL,
    PRIMARY KEY (camera_id, "time", person_id)
) PARTITION BY RANGE ("time");
CREATE INDEX idx_tracking_camera_time ON tracking_coordinates(camera_id, "time" DESC);

CREATE TABLE zone_dwell_sessions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id       UUID NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    person_id     TEXT NOT NULL,
    entered_at    TIMESTAMPTZ NOT NULL,
    exited_at     TIMESTAMPTZ,
    dwell_seconds INTEGER,
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_zone_dwell_zone_id ON zone_dwell_sessions(zone_id);

CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NULL REFERENCES tenants(id) ON DELETE CASCADE,
    reseller_id UUID NULL REFERENCES resellers(id) ON DELETE CASCADE,
    partner_id  UUID NULL REFERENCES partners(id) ON DELETE CASCADE,
    email       CITEXT NOT NULL UNIQUE,
    role        TEXT NOT NULL CHECK (role IN ('admin','operator','viewer')),
    status      TEXT NOT NULL DEFAULT 'invited' CHECK (status IN ('active','invited','disabled')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_partner_requires_tenant CHECK (partner_id IS NULL OR tenant_id IS NOT NULL),
    CONSTRAINT chk_user_not_dual_scope     CHECK (NOT (tenant_id IS NOT NULL AND reseller_id IS NOT NULL))
);
CREATE INDEX idx_users_tenant_id   ON users(tenant_id);
CREATE INDEX idx_users_reseller_id ON users(reseller_id);
CREATE INDEX idx_users_partner_id  ON users(partner_id);

CREATE TABLE user_site_assignments (
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    site_id     UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, site_id)
);
CREATE INDEX idx_usa_site_id ON user_site_assignments(site_id);

-- Section 8.0 supplementary tables
CREATE TABLE model_registry_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vertical_type   TEXT NOT NULL CHECK (vertical_type IN ('retail','banking','logistics')),
    version         TEXT NOT NULL,
    s3_key          TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    released_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_current      BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE edge_gateways (
    id                    TEXT PRIMARY KEY,
    site_id               UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    vertical_type         TEXT NOT NULL,
    current_model_version TEXT,
    channel               TEXT NOT NULL DEFAULT 'stable' CHECK (channel IN ('stable','canary')),
    last_heartbeat_at     TIMESTAMPTZ,
    status                TEXT NOT NULL DEFAULT 'offline' CHECK (status IN ('online','offline','degraded'))
);
CREATE INDEX idx_edge_gateways_site_id ON edge_gateways(site_id);

-- Section 8.5: break-glass audit infrastructure
CREATE TABLE platform_admins (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email      CITEXT NOT NULL UNIQUE,
    status     TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled'))
);

CREATE TABLE break_glass_audit_log (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_admin_id  UUID NOT NULL REFERENCES platform_admins(id),
    reason             TEXT NOT NULL,
    ticket_id          TEXT NOT NULL,
    tenant_id_accessed UUID NOT NULL,
    started_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at           TIMESTAMPTZ
);
""")

    # ── SECURITY DEFINER helpers (break RLS mutual recursion — Section 8.3) ──
    op.execute("""
CREATE OR REPLACE FUNCTION sec_tenant_owns_site(p_site UUID, p_tenant UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM sites s WHERE s.id = p_site AND s.tenant_id = p_tenant)
$$;

CREATE OR REPLACE FUNCTION sec_tenant_owns_camera(p_cam UUID, p_tenant UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM cameras c JOIN sites s ON s.id = c.site_id
    WHERE c.id = p_cam AND s.tenant_id = p_tenant
  )
$$;

CREATE OR REPLACE FUNCTION sec_partner_has_zone_on_site(p_site UUID, p_partner UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM zones z JOIN cameras c ON c.id = z.camera_id
    WHERE c.site_id = p_site AND z.owner_type = 'PARTNER' AND z.owner_partner_id = p_partner
  )
$$;

CREATE OR REPLACE FUNCTION sec_partner_has_zone_on_camera(p_cam UUID, p_partner UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM zones z
    WHERE z.camera_id = p_cam AND z.owner_type = 'PARTNER' AND z.owner_partner_id = p_partner
  )
$$;

CREATE OR REPLACE FUNCTION sec_partner_belongs_to_tenant(p_partner UUID, p_tenant UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM partners p WHERE p.id = p_partner AND p.tenant_id = p_tenant)
$$;

-- Break-glass check wrapped in SECURITY DEFINER so traxia_app never needs SELECT
-- on break_glass_audit_log / platform_admins directly. Without this, the EXISTS
-- in the policy causes "permission denied" even when the IS NOT NULL guard is false,
-- because PostgreSQL validates object permissions at plan time.
CREATE OR REPLACE FUNCTION sec_break_glass_allows_camera(p_cam UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT
    current_setting('app.break_glass_admin_id', true) IS NOT NULL
    AND current_setting('app.break_glass_admin_id', true) <> ''
    AND EXISTS (
      SELECT 1
      FROM break_glass_audit_log b
      JOIN platform_admins pa ON pa.id = b.platform_admin_id AND pa.status = 'active'
      JOIN cameras  c ON c.id  = p_cam
      JOIN sites    s ON s.id  = c.site_id
      WHERE b.platform_admin_id = current_setting('app.break_glass_admin_id', true)::UUID
        AND b.tenant_id_accessed = s.tenant_id
        AND b.ended_at IS NULL
        AND b.started_at > now() - interval '4 hours'
    )
$$;
""")

    # ── RLS: ENABLE + FORCE on all tables (Section 8.3) ──────────────────────
    op.execute("""
-- resellers
ALTER TABLE resellers ENABLE ROW LEVEL SECURITY;
ALTER TABLE resellers FORCE ROW LEVEL SECURITY;
CREATE POLICY resellers_read ON resellers
  FOR SELECT USING (id = app_current_reseller_id());

-- tenants
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenants_read ON tenants
  FOR SELECT USING (
    (app_current_partner_id() IS NULL AND app_current_reseller_id() IS NULL
      AND tenants.id = app_current_tenant_id())
    OR (app_current_partner_id() IS NOT NULL
      AND sec_partner_belongs_to_tenant(app_current_partner_id(), tenants.id))
    OR (app_current_reseller_id() IS NOT NULL
      AND tenants.reseller_id = app_current_reseller_id())
  );

-- partners
ALTER TABLE partners ENABLE ROW LEVEL SECURITY;
ALTER TABLE partners FORCE ROW LEVEL SECURITY;
CREATE POLICY partners_read ON partners
  FOR SELECT USING (
    (app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND partners.tenant_id = app_current_tenant_id())
    OR (partners.id = app_current_partner_id())
  );
CREATE POLICY partners_write ON partners
  FOR INSERT WITH CHECK (
    app_current_partner_id() IS NULL AND app_current_role() = 'admin'
    AND partners.tenant_id = app_current_tenant_id()
  );
CREATE POLICY partners_update ON partners
  FOR UPDATE USING (
    app_current_partner_id() IS NULL AND app_current_role() = 'admin'
    AND partners.tenant_id = app_current_tenant_id()
  );

-- sites
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE sites FORCE ROW LEVEL SECURITY;
CREATE POLICY sites_read ON sites
  FOR SELECT USING (
    (app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND sites.tenant_id = app_current_tenant_id())
    OR (app_current_partner_id() IS NULL AND app_current_role() IN ('operator','viewer')
      AND sites.id = ANY(app_current_site_ids()))
    OR (app_current_partner_id() IS NOT NULL
      AND sec_partner_has_zone_on_site(sites.id, app_current_partner_id()))
  );
CREATE POLICY sites_provision ON sites
  FOR INSERT WITH CHECK (sites.tenant_id = app_provision_tenant_id());

-- cameras
ALTER TABLE cameras ENABLE ROW LEVEL SECURITY;
ALTER TABLE cameras FORCE ROW LEVEL SECURITY;
CREATE POLICY cameras_read ON cameras
  FOR SELECT USING (
    (app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND sec_tenant_owns_camera(cameras.id, app_current_tenant_id()))
    OR (app_current_partner_id() IS NULL AND app_current_role() IN ('operator','viewer')
      AND cameras.site_id = ANY(app_current_site_ids()))
    OR (app_current_partner_id() IS NOT NULL
      AND sec_partner_has_zone_on_camera(cameras.id, app_current_partner_id()))
  );
CREATE POLICY cameras_provision ON cameras
  FOR INSERT WITH CHECK (sec_tenant_owns_site(cameras.site_id, app_provision_tenant_id()));

-- zones
ALTER TABLE zones ENABLE ROW LEVEL SECURITY;
ALTER TABLE zones FORCE ROW LEVEL SECURITY;
CREATE POLICY zones_read ON zones
  FOR SELECT USING (
    (app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND (
        (zones.owner_type = 'TENANT'  AND zones.owner_tenant_id = app_current_tenant_id())
        OR (zones.owner_type = 'PARTNER'
          AND sec_partner_belongs_to_tenant(zones.owner_partner_id, app_current_tenant_id()))
      ))
    OR (app_current_partner_id() IS NULL AND app_current_role() IN ('operator','viewer')
      AND EXISTS (
        SELECT 1 FROM cameras c WHERE c.id = zones.camera_id
          AND c.site_id = ANY(app_current_site_ids())
      ))
    OR (zones.owner_type = 'PARTNER' AND zones.owner_partner_id = app_current_partner_id())
  );
CREATE POLICY zones_update ON zones
  FOR UPDATE USING (
    app_current_partner_id() IS NULL AND app_current_role() = 'admin'
    AND sec_tenant_owns_camera(zones.camera_id, app_current_tenant_id())
  );
CREATE POLICY zones_provision ON zones
  FOR INSERT WITH CHECK (sec_tenant_owns_camera(zones.camera_id, app_provision_tenant_id()));

-- tracking_coordinates (partitioned — policies apply to all partitions)
ALTER TABLE tracking_coordinates ENABLE ROW LEVEL SECURITY;
ALTER TABLE tracking_coordinates FORCE ROW LEVEL SECURITY;
CREATE POLICY tracking_coordinates_isolation ON tracking_coordinates
  FOR SELECT USING (
    (app_current_partner_id() IS NOT NULL AND EXISTS (
      SELECT 1 FROM zones z
      WHERE z.camera_id = tracking_coordinates.camera_id
        AND z.owner_type = 'PARTNER' AND z.owner_partner_id = app_current_partner_id()
    ))
    OR (app_current_partner_id() IS NULL AND app_current_role() = 'admin' AND EXISTS (
      SELECT 1 FROM cameras c JOIN sites s ON s.id = c.site_id
      WHERE c.id = tracking_coordinates.camera_id AND s.tenant_id = app_current_tenant_id()
    ))
    OR (app_current_partner_id() IS NULL AND app_current_role() IN ('operator','viewer') AND EXISTS (
      SELECT 1 FROM cameras c
      WHERE c.id = tracking_coordinates.camera_id AND c.site_id = ANY(app_current_site_ids())
    ))
  );
CREATE POLICY tracking_coordinates_ingest ON tracking_coordinates
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM cameras c
      WHERE c.id = tracking_coordinates.camera_id
        AND c.site_id = app_current_ingest_site_id()
    )
  );
CREATE POLICY tracking_coordinates_break_glass ON tracking_coordinates
  FOR SELECT USING (sec_break_glass_allows_camera(tracking_coordinates.camera_id));

-- zone_dwell_sessions
ALTER TABLE zone_dwell_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE zone_dwell_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY zone_dwell_sessions_isolation ON zone_dwell_sessions
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM zones z WHERE z.id = zone_dwell_sessions.zone_id AND (
        (z.owner_type = 'TENANT' AND app_current_partner_id() IS NULL
          AND z.owner_tenant_id = app_current_tenant_id())
        OR
        (z.owner_type = 'PARTNER' AND app_current_partner_id() IS NULL
          AND EXISTS (
            SELECT 1 FROM partners p
            WHERE p.id = z.owner_partner_id AND p.tenant_id = app_current_tenant_id()
          ))
        OR
        (z.owner_type = 'PARTNER' AND app_current_partner_id() IS NOT NULL
          AND z.owner_partner_id = app_current_partner_id())
      )
    )
  );
CREATE POLICY zone_dwell_sessions_ingest ON zone_dwell_sessions
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM zones z JOIN cameras c ON c.id = z.camera_id
      WHERE z.id = zone_dwell_sessions.zone_id AND c.site_id = app_motor_site_id()
    )
  );

-- users
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_read ON users
  FOR SELECT USING (
    (users.id = app_current_user_id())
    OR (app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND users.tenant_id = app_current_tenant_id())
    OR (app_current_partner_id() IS NOT NULL AND app_current_role() = 'admin'
      AND users.partner_id = app_current_partner_id())
    OR (app_current_reseller_id() IS NOT NULL
      AND users.reseller_id = app_current_reseller_id())
  );
CREATE POLICY users_write ON users
  FOR INSERT WITH CHECK (
    app_current_role() = 'admin' AND (
      (app_current_partner_id() IS NULL AND users.tenant_id = app_current_tenant_id())
      OR (app_current_partner_id() IS NOT NULL AND users.partner_id = app_current_partner_id())
    )
  );

-- user_site_assignments
ALTER TABLE user_site_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_site_assignments FORCE ROW LEVEL SECURITY;
CREATE POLICY usa_read ON user_site_assignments
  FOR SELECT USING (
    (user_site_assignments.user_id = app_current_user_id())
    OR (app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND sec_tenant_owns_site(user_site_assignments.site_id, app_current_tenant_id()))
  );
CREATE POLICY usa_write ON user_site_assignments
  FOR INSERT WITH CHECK (
    app_current_partner_id() IS NULL AND app_current_role() = 'admin'
    AND sec_tenant_owns_site(user_site_assignments.site_id, app_current_tenant_id())
  );

-- platform_admins / break_glass_audit_log: deny-by-default for all app roles.
-- Only accessible via a superuser/BYPASSRLS channel (internal platform ops).
ALTER TABLE platform_admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_admins FORCE ROW LEVEL SECURITY;
ALTER TABLE break_glass_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE break_glass_audit_log FORCE ROW LEVEL SECURITY;

-- model_registry_entries / edge_gateways: deny-by-default for traxia_app.
-- traxia_service (created below) is the only role with access policies.
-- MLP access pattern: backend service processes connect as traxia_service,
-- NOT as traxia_app; traxia_app is the tenant-scoped application role only.
ALTER TABLE model_registry_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_registry_entries FORCE ROW LEVEL SECURITY;
ALTER TABLE edge_gateways ENABLE ROW LEVEL SECURITY;
ALTER TABLE edge_gateways FORCE ROW LEVEL SECURITY;
""")

    # ── Application roles ─────────────────────────────────────────────────────
    op.execute("""
-- traxia_app: tenant-scoped role for all user-facing queries. RLS enforced.
DO $$ BEGIN
  CREATE ROLE traxia_app NOINHERIT NOLOGIN;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

GRANT USAGE ON SCHEMA public TO traxia_app;
GRANT SELECT, INSERT, UPDATE ON
    resellers, tenants, partners, sites, cameras, zones,
    tracking_coordinates, zone_dwell_sessions,
    users, user_site_assignments
  TO traxia_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO traxia_app;
DO $$ BEGIN
  EXECUTE format('GRANT TEMPORARY ON DATABASE %I TO traxia_app', current_database());
END $$;

-- traxia_service: internal backend role (Model Manager, fleet heartbeat).
-- Connects via a separate credential pool; never exposed to tenant sessions.
-- RLS enforced — access is granted via explicit policies below, not BYPASSRLS.
DO $$ BEGIN
  CREATE ROLE traxia_service NOINHERIT NOLOGIN;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

GRANT USAGE ON SCHEMA public TO traxia_service;
GRANT SELECT, INSERT, UPDATE ON model_registry_entries, edge_gateways TO traxia_service;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO traxia_service;
""")

    # ── pg_partman: monthly partitions, 13-month retention (Section 8.6) ─────
    op.execute("""
SELECT partman.create_parent(
  p_parent_table := 'public.tracking_coordinates',
  p_control      := 'time',
  p_interval     := '1 month',
  p_premake      := 3
);

UPDATE partman.part_config
   SET retention                = '13 months',
       retention_keep_table     = false,
       infinite_time_partitions = true
 WHERE parent_table = 'public.tracking_coordinates';
""")

    # ── RLS policies for traxia_service on internal tables ───────────────────
    # model_registry_entries: platform-level data (no per-tenant scope).
    # Readable/writable only by traxia_service; traxia_app gets zero rows.
    op.execute("""
CREATE POLICY model_registry_service_read ON model_registry_entries
  FOR SELECT TO traxia_service USING (true);
CREATE POLICY model_registry_service_write ON model_registry_entries
  FOR INSERT TO traxia_service WITH CHECK (true);
CREATE POLICY model_registry_service_update ON model_registry_entries
  FOR UPDATE TO traxia_service USING (true);

-- edge_gateways: traxia_service reads/writes all rows (fleet management,
-- heartbeat updates). The Edge Gateway itself never connects to Postgres
-- directly in the MLP — it goes through the Cloud API, which runs as
-- traxia_service when touching these tables.
CREATE POLICY edge_gateways_service_read ON edge_gateways
  FOR SELECT TO traxia_service USING (true);
CREATE POLICY edge_gateways_service_write ON edge_gateways
  FOR INSERT TO traxia_service WITH CHECK (true);
CREATE POLICY edge_gateways_service_update ON edge_gateways
  FOR UPDATE TO traxia_service USING (true);
""")

    # ── Views with security_invoker (Section 8.1) ─────────────────────────────
    op.execute("""
CREATE VIEW site_traffic_daily
WITH (security_invoker = true) AS
SELECT
    c.site_id,
    date_trunc('day', tc."time")       AS day,
    count(DISTINCT tc.person_id)       AS unique_visitors,
    count(*)                           AS total_detections
FROM tracking_coordinates tc
JOIN cameras c ON c.id = tc.camera_id
GROUP BY c.site_id, date_trunc('day', tc."time");

CREATE VIEW site_traffic_comparison
WITH (security_invoker = true) AS
SELECT
    s.id   AS site_id,
    s.name AS site_name,
    date_trunc('week', tc."time")      AS week,
    count(DISTINCT tc.person_id)       AS unique_visitors
FROM tracking_coordinates tc
JOIN cameras c ON c.id = tc.camera_id
JOIN sites   s ON s.id = c.site_id
GROUP BY s.id, s.name, date_trunc('week', tc."time");
""")


def downgrade() -> None:
    op.execute("""
DROP VIEW IF EXISTS site_traffic_comparison;
DROP VIEW IF EXISTS site_traffic_daily;

DROP TABLE IF EXISTS break_glass_audit_log CASCADE;
DROP TABLE IF EXISTS platform_admins       CASCADE;
DROP TABLE IF EXISTS edge_gateways         CASCADE;
DROP TABLE IF EXISTS model_registry_entries CASCADE;
DROP TABLE IF EXISTS user_site_assignments  CASCADE;
DROP TABLE IF EXISTS users                  CASCADE;
DROP TABLE IF EXISTS zone_dwell_sessions    CASCADE;
DROP TABLE IF EXISTS tracking_coordinates   CASCADE;
DROP TABLE IF EXISTS zones                  CASCADE;
DROP TABLE IF EXISTS cameras                CASCADE;
DROP TABLE IF EXISTS sites                  CASCADE;
DROP TABLE IF EXISTS partners               CASCADE;
DROP TABLE IF EXISTS tenants                CASCADE;
DROP TABLE IF EXISTS resellers              CASCADE;

DROP FUNCTION IF EXISTS sec_break_glass_allows_camera(UUID);
DROP FUNCTION IF EXISTS sec_partner_belongs_to_tenant(UUID, UUID);
DROP FUNCTION IF EXISTS sec_partner_has_zone_on_camera(UUID, UUID);
DROP FUNCTION IF EXISTS sec_partner_has_zone_on_site(UUID, UUID);
DROP FUNCTION IF EXISTS sec_tenant_owns_camera(UUID, UUID);
DROP FUNCTION IF EXISTS sec_tenant_owns_site(UUID, UUID);
DROP FUNCTION IF EXISTS app_motor_site_id();
DROP FUNCTION IF EXISTS app_current_ingest_site_id();
DROP FUNCTION IF EXISTS app_provision_tenant_id();
DROP FUNCTION IF EXISTS app_current_user_id();
DROP FUNCTION IF EXISTS app_current_reseller_id();
DROP FUNCTION IF EXISTS app_current_site_ids();
DROP FUNCTION IF EXISTS app_current_role();
DROP FUNCTION IF EXISTS app_current_partner_id();
DROP FUNCTION IF EXISTS app_current_tenant_id();

DROP ROLE IF EXISTS traxia_service;
DROP ROLE IF EXISTS traxia_app;
""")
