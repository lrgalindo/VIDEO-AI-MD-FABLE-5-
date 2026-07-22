-- Test (§8.6): tracking_coordinates ingest is isolated per site.
--
-- Attack scenario: a gateway authenticated to Site A (Tienda A) sends a
-- tracking event whose camera_id belongs to Site B (Tienda B / different tenant).
-- The tracking_coordinates_ingest policy calls sec_camera_on_ingest_site(),
-- which checks  cameras.site_id = app_current_ingest_site_id().
-- Because the ingest context carries site_A's UUID and the camera belongs to
-- site_B, the EXISTS subquery returns false → INSERT is rejected with 42501.
--
-- This test also verifies the reverse: a Site B ingest context cannot insert
-- events for Site A's cameras.
--
-- Runs inside BEGIN/ROLLBACK so no data persists.  Seed is fully self-contained.

BEGIN;

-- ── Plan ─────────────────────────────────────────────────────────────────

SELECT plan(5);

-- ── Seed (superuser — RLS bypassed for postgres, so all INSERTs succeed) ─

INSERT INTO resellers (id, name) VALUES
  ('07000000-0000-0000-0000-000000000001', 'Test Reseller Isolation 07');

INSERT INTO tenants (id, reseller_id, name, vertical_type, status) VALUES
  ('07100000-0000-0000-0000-000000000001', '07000000-0000-0000-0000-000000000001', 'Tienda A', 'retail', 'active'),
  ('07200000-0000-0000-0000-000000000001', '07000000-0000-0000-0000-000000000001', 'Tienda B', 'retail', 'active');

INSERT INTO sites (id, tenant_id, name, status) VALUES
  ('07100000-0000-0000-0000-000000000002', '07100000-0000-0000-0000-000000000001', 'Site A', 'active'),
  ('07200000-0000-0000-0000-000000000002', '07200000-0000-0000-0000-000000000001', 'Site B', 'active');

INSERT INTO cameras (id, site_id, name, rtsp_url_ciphertext, rtsp_url_key_id, status) VALUES
  ('07100000-0000-0000-0000-000000000003', '07100000-0000-0000-0000-000000000002', 'Camera A',
   decode('6741414141414271594251683734674b484f766b50626f3078313433307857334a6a445f4c44776d36434658324c63587639446d6e437372556c37695554634233365763666d694d674d4178516e4377464d4e66357373436a6545714662564f483356564c4c4c575964485639515f4d2d356a744c49673d', 'hex'),
   'test-key-v1', 'active'),
  ('07200000-0000-0000-0000-000000000003', '07200000-0000-0000-0000-000000000002', 'Camera B',
   decode('6741414141414271594251685472304743716e756a33374c3671466e6146447a4f674d5931314632345a695233376c397a6a4533485078727a6945344a466337524b33744145314e6c656a4143506a5a5f6d7849475962643076634f2d6652665444565a4f576a5557735f765f4c345a6d373573554c343d', 'hex'),
   'test-key-v1', 'active');

-- ── Switch to traxia_app with Site A's ingest context ────────────────────
-- This mirrors what the telemetry ingest endpoint does after verifying the JWT:
--   SET ROLE traxia_app
--   SET LOCAL app.current_ingest_site_id = <jwt.sid>  ← site_A's UUID

SET LOCAL ROLE traxia_app;
SET LOCAL app.current_ingest_site_id = '07100000-0000-0000-0000-000000000002';

-- (1) Gateway A inserting an event for its own camera (Camera A) must succeed.
SELECT lives_ok(
  $$
  INSERT INTO tracking_coordinates (camera_id, "time", person_id, x, y)
  VALUES ('07100000-0000-0000-0000-000000000003', now(), 'person-001', 100, 200)
  $$,
  'Site-A gateway can insert event for its own camera (Camera A)'
);

-- (2) Same gateway, same Site-A ingest context, but camera_id belongs to Site B.
--     sec_camera_on_ingest_site('Camera B') →
--       cameras WHERE id=Camera_B AND site_id=site_A → no rows → false
--     → RLS WITH CHECK fails → 42501 insufficient_privilege
SELECT throws_ok(
  $$
  INSERT INTO tracking_coordinates (camera_id, "time", person_id, x, y)
  VALUES ('07200000-0000-0000-0000-000000000003', now(), 'person-001', 100, 200)
  $$,
  '42501',
  'new row violates row-level security policy for table "tracking_coordinates"',
  'Site-A gateway cannot insert event for Site-B camera (cross-tenant rejected by RLS)'
);

-- ── Switch to Site B's ingest context (mirrors another gateway's JWT) ────

SET LOCAL app.current_ingest_site_id = '07200000-0000-0000-0000-000000000002';

-- (3) With Site-B context, Camera A (which belongs to Site A) must also be rejected.
SELECT throws_ok(
  $$
  INSERT INTO tracking_coordinates (camera_id, "time", person_id, x, y)
  VALUES ('07100000-0000-0000-0000-000000000003', now(), 'person-002', 150, 250)
  $$,
  '42501',
  'new row violates row-level security policy for table "tracking_coordinates"',
  'Site-B gateway cannot insert event for Site-A camera (cross-tenant, opposite direction, also rejected)'
);

-- (4) Camera B with Site-B context must succeed (site matches).
SELECT lives_ok(
  $$
  INSERT INTO tracking_coordinates (camera_id, "time", person_id, x, y)
  VALUES ('07200000-0000-0000-0000-000000000003', now(), 'person-002', 150, 250)
  $$,
  'Site-B gateway can insert event for its own camera (Camera B)'
);

-- (5) A completely unknown camera_id (not in any site) is also rejected.
SET LOCAL app.current_ingest_site_id = '07100000-0000-0000-0000-000000000002';
SELECT throws_ok(
  $$
  INSERT INTO tracking_coordinates (camera_id, "time", person_id, x, y)
  VALUES ('ffffffff-ffff-ffff-ffff-ffffffffffff', now(), 'person-001', 10, 20)
  $$,
  '42501',
  'new row violates row-level security policy for table "tracking_coordinates"',
  'Unknown camera_id is rejected (no camera row → sec_camera_on_ingest_site returns false)'
);

SELECT * FROM finish();

ROLLBACK;
