-- Tests: Analytics RLS isolation — site-level and cross-tenant scoping.
--
-- Protects: GET /v1/analytics/traffic (site_traffic_daily)
--           GET /v1/analytics/comparison (aggregated over site_traffic_daily)
--
-- site_traffic_daily is a SECURITY INVOKER view that inherits the `sites` table
-- RLS policy. These tests verify that RLS on `sites` enforces the filtering:
--   • Tenant isolation: operator cannot see any site from another tenant.
--   • Within-tenant site scoping: operator with sids=[site_a1] cannot see
--     site_a2 (a different site in the same tenant).
--   • Admin exception: tenant admin sees all sites in the tenant.
--   • Partner scoping: partner viewer only sees their own partner's zones,
--     not zones of other partners in the same tenant.
--
-- Coverage:
--   (1) Operator (sids=[site_a1]) sees site_a1
--   (2) Operator (sids=[site_a1]) does NOT see site_a2 (within-tenant isolation)
--   (3) Operator (sids=[site_a1]) does NOT see site_b1 (cross-tenant isolation)
--   (4) Admin sees both site_a1 and site_a2 (tenant-wide access)
--   (5) Admin does NOT see site_b1 (cross-tenant isolation even for admin)
--   (6) Partner Viewer (pid=partner_p) sees zones from partner_p only
--   (7) Partner Viewer (pid=partner_p) does NOT see zones from partner_q

BEGIN;

SELECT plan(7);

-- ── Seeded IDs (from 00_backoffice_seed.sql) ──────────────────────────────────
-- tenant_a : bb100000-0000-4000-8000-000000000001
-- tenant_b : bb200000-0000-4000-8000-000000000001
-- site_a1  : bb100000-0000-4000-8000-000000000002  (Tenant A)
-- site_a2  : bb100000-0000-4000-8000-000000000003  (Tenant A — different site)
-- site_b1  : bb200000-0000-4000-8000-000000000002  (Tenant B)
-- cam_a1   : bb100000-0000-4000-8000-000000000004  (Camera on site_a1)
-- admin_a  : bb100000-0000-4000-8000-000000000010

-- ── Set up: add a second camera on site_a2 and two partner zones ───────────────
-- (Runs as superuser before we switch to traxia_app)
INSERT INTO cameras (id, site_id, name, rtsp_url_ciphertext, rtsp_url_key_id, status)
VALUES ('bb100000-0000-4000-8000-000000000005',
        'bb100000-0000-4000-8000-000000000003',
        'Cam A-2',
        decode('6741414141414271594251685472304743716e756a33374c3671466e6146447a4f674d5931314632345a695233376c397a6a4533485078727a6945344a466337524b33744145314e6c656a4143506a5a5f6d7849475962643076634f2d6652665444565a4f576a5557735f765f4c345a6d373573554c343d', 'hex'),
        'test-key-v1', 'active')
ON CONFLICT DO NOTHING;

-- Two partners in Tenant A for zone scoping tests
INSERT INTO partners (id, tenant_id, name, status)
VALUES ('bb300000-0000-0000-0000-000000000001', 'bb100000-0000-4000-8000-000000000001', 'Partner P', 'active'),
       ('bb300000-0000-0000-0000-000000000002', 'bb100000-0000-4000-8000-000000000001', 'Partner Q', 'active')
ON CONFLICT DO NOTHING;

-- Users for each partner
INSERT INTO users (id, tenant_id, partner_id, email, role, status)
VALUES
  ('bb310000-0000-0000-0000-000000000001',
   'bb100000-0000-4000-8000-000000000001',
   'bb300000-0000-0000-0000-000000000001',
   'pv-p@test.com', 'viewer', 'active'),
  ('bb310000-0000-0000-0000-000000000002',
   'bb100000-0000-4000-8000-000000000001',
   'bb300000-0000-0000-0000-000000000002',
   'pv-q@test.com', 'viewer', 'active')
ON CONFLICT DO NOTHING;

-- One zone per partner (both on cam_a1 to isolate the partner filter, not camera filter)
INSERT INTO zones (id, camera_id, owner_type, owner_partner_id, owner_tenant_id, name, zone_type, coordinates)
VALUES
  ('bb320000-0000-0000-0000-000000000001',
   'bb100000-0000-4000-8000-000000000004',
   'PARTNER', 'bb300000-0000-0000-0000-000000000001', 'bb100000-0000-4000-8000-000000000001',
   'Zone P1', 'shelf',
   '{"type":"polygon","points":[[0,0],[50,0],[50,50],[0,50]]}'::jsonb),
  ('bb320000-0000-0000-0000-000000000002',
   'bb100000-0000-4000-8000-000000000004',
   'PARTNER', 'bb300000-0000-0000-0000-000000000002', 'bb100000-0000-4000-8000-000000000001',
   'Zone Q1', 'shelf',
   '{"type":"polygon","points":[[100,0],[150,0],[150,50],[100,50]]}'::jsonb)
ON CONFLICT DO NOTHING;

-- ── Switch to traxia_app role for all subsequent queries ─────────────────────
SET LOCAL ROLE traxia_app;
SET LOCAL app.current_tenant_id  = 'bb100000-0000-4000-8000-000000000001';
SET LOCAL app.current_actor_role = 'operator';
SET LOCAL app.current_user_id    = 'bb100000-0000-4000-8000-000000000010';

-- Operator assigned ONLY to site_a1
SET LOCAL app.current_user_site_ids = 'bb100000-0000-4000-8000-000000000002';

-- (1) Operator sees site_a1
SELECT is(
  (SELECT count(*)::integer FROM sites WHERE id = 'bb100000-0000-4000-8000-000000000002'),
  1,
  'Operator with sids=[site_a1] can see site_a1'
);

-- (2) Operator does NOT see site_a2 (same tenant, not in sids)
SELECT is(
  (SELECT count(*)::integer FROM sites WHERE id = 'bb100000-0000-4000-8000-000000000003'),
  0,
  'Operator with sids=[site_a1] cannot see site_a2 (within-tenant cross-site isolation)'
);

-- (3) Operator does NOT see site_b1 (different tenant entirely)
SELECT is(
  (SELECT count(*)::integer FROM sites WHERE id = 'bb200000-0000-4000-8000-000000000002'),
  0,
  'Operator with sids=[site_a1] cannot see site_b1 (cross-tenant isolation)'
);

-- ── Switch to admin for tests (4) and (5) ────────────────────────────────────
SET LOCAL app.current_actor_role    = 'admin';
SET LOCAL app.current_user_site_ids = '';

-- (4) Admin sees both site_a1 and site_a2 (tenant-wide)
SELECT is(
  (SELECT count(*)::integer FROM sites
   WHERE id IN ('bb100000-0000-4000-8000-000000000002',
                'bb100000-0000-4000-8000-000000000003')),
  2,
  'Tenant admin sees all tenant sites (site_a1 + site_a2)'
);

-- (5) Admin does NOT see site_b1 (cross-tenant boundary holds even for admin)
SELECT is(
  (SELECT count(*)::integer FROM sites WHERE id = 'bb200000-0000-4000-8000-000000000002'),
  0,
  'Tenant admin cannot see site_b1 (cross-tenant isolation holds for admin too)'
);

-- ── Switch to Partner P viewer context ───────────────────────────────────────
SET LOCAL app.current_actor_role = 'viewer';
SET LOCAL app.current_partner_id = 'bb300000-0000-0000-0000-000000000001';
SET LOCAL app.current_user_id    = 'bb310000-0000-0000-0000-000000000001';

-- (6) Partner P viewer sees only Partner P's zone (Zone P1)
SELECT is(
  (SELECT count(*)::integer FROM zones
   WHERE id = 'bb320000-0000-0000-0000-000000000001'),
  1,
  'Partner P viewer sees Partner P zone (Zone P1)'
);

-- (7) Partner P viewer does NOT see Partner Q's zone (Zone Q1)
SELECT is(
  (SELECT count(*)::integer FROM zones
   WHERE id = 'bb320000-0000-0000-0000-000000000002'),
  0,
  'Partner P viewer cannot see Partner Q zone (cross-partner isolation within same tenant)'
);

SELECT * FROM finish();

ROLLBACK;
