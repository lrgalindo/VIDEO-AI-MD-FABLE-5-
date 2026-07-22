-- Seed data for pgTAP isolation tests (Section 8.4 UUIDs)
-- Safe to run multiple times (ON CONFLICT DO NOTHING).

INSERT INTO resellers (id, name) VALUES
  ('00000000-0000-4000-8000-0000000000e1', 'Reseller Demo Centroamérica')
ON CONFLICT DO NOTHING;

INSERT INTO tenants (id, reseller_id, name, vertical_type, status) VALUES
  ('00000000-0000-4000-8000-0000000000a1',
   '00000000-0000-4000-8000-0000000000e1', 'La Torre (retail demo)', 'retail',  'active'),
  ('00000000-0000-4000-8000-0000000000a2',
   NULL,                                   'Banco Demo',             'banking', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO sites (id, tenant_id, name, status) VALUES
  ('00000000-0000-4000-8000-0000000000b1', '00000000-0000-4000-8000-0000000000a1', 'La Torre Zona 10',     'active'),
  ('00000000-0000-4000-8000-0000000000b2', '00000000-0000-4000-8000-0000000000a1', 'La Torre Zona 4',      'active'),
  ('00000000-0000-4000-8000-0000000000b3', '00000000-0000-4000-8000-0000000000a2', 'Sucursal Banco Centro', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO partners (id, tenant_id, name, status) VALUES
  ('00000000-0000-4000-8000-0000000000d1',
   '00000000-0000-4000-8000-0000000000a1', 'Nestlé Demo',     'active'),
  ('00000000-0000-4000-8000-0000000000d2',
   '00000000-0000-4000-8000-0000000000a1', 'Coca-Cola Demo',  'active')
ON CONFLICT DO NOTHING;

INSERT INTO users (id, tenant_id, email, role, status) VALUES
  ('00000000-0000-4000-8000-0000000000c1', '00000000-0000-4000-8000-0000000000a1', 'admin@qa.demo',    'admin',    'active'),
  ('00000000-0000-4000-8000-0000000000c2', '00000000-0000-4000-8000-0000000000a1', 'operator@qa.demo', 'operator', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO users (id, tenant_id, partner_id, email, role, status) VALUES
  ('00000000-0000-4000-8000-0000000000c3',
   '00000000-0000-4000-8000-0000000000a1',
   '00000000-0000-4000-8000-0000000000d1',
   'viewer@partner.demo', 'viewer', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO user_site_assignments (user_id, site_id) VALUES
  ('00000000-0000-4000-8000-0000000000c2', '00000000-0000-4000-8000-0000000000b1')
ON CONFLICT DO NOTHING;

-- One camera per site (rtsp_url_ciphertext: Fernet-encrypted with TEST_RTSP_ENCRYPTION_KEY)
INSERT INTO cameras (id, site_id, name, rtsp_url_ciphertext, rtsp_url_key_id, status) VALUES
  ('00000000-0000-4000-8000-00000000f101', '00000000-0000-4000-8000-0000000000b1', 'Cam-Z10-001',
   decode('6741414141414271594251683734674b484f766b50626f3078313433307857334a6a445f4c44776d36434658324c63587639446d6e437372556c37695554634233365763666d694d674d4178516e4377464d4e66357373436a6545714662564f483356564c4c4c575964485639515f4d2d356a744c49673d', 'hex'),
   'test-key-v1', 'active'),
  ('00000000-0000-4000-8000-00000000f102', '00000000-0000-4000-8000-0000000000b2', 'Cam-Z4-001',
   decode('6741414141414271594251685472304743716e756a33374c3671466e6146447a4f674d5931314632345a695233376c397a6a4533485078727a6945344a466337524b33744145314e6c656a4143506a5a5f6d7849475962643076634f2d6652665444565a4f576a5557735f765f4c345a6d373573554c343d', 'hex'),
   'test-key-v1', 'active'),
  ('00000000-0000-4000-8000-00000000f103', '00000000-0000-4000-8000-0000000000b3', 'Cam-Banco-001',
   decode('6741414141414271594251686c4263795630335936665750504161667364773148374277454e6d71794d33574344564c666e4a70644b576f72304549773337794a59466a447672674134427450376459467a39554858506d38324c6f467331642d303330514b466f414c4154646355727a67376c3652343d', 'hex'),
   'test-key-v1', 'active')
ON CONFLICT DO NOTHING;

-- TENANT-owned zone (camera in site b1 / Zona 10)
INSERT INTO zones (id, camera_id, owner_type, owner_tenant_id, name, zone_type, coordinates)
VALUES (
  '00000000-0000-4000-8000-00000000e101',
  '00000000-0000-4000-8000-00000000f101',
  'TENANT', '00000000-0000-4000-8000-0000000000a1',
  'Zona Entrada Z10', 'entrance', '[[0,0],[100,0],[100,100],[0,100]]'
) ON CONFLICT DO NOTHING;

-- PARTNER-owned zone for d1 (same camera f101)
INSERT INTO zones (id, camera_id, owner_type, owner_partner_id, name, zone_type, coordinates)
VALUES (
  '00000000-0000-4000-8000-00000000e102',
  '00000000-0000-4000-8000-00000000f101',
  'PARTNER', '00000000-0000-4000-8000-0000000000d1',
  'Góndola Nestlé Z10', 'shelf', '[[100,0],[200,0],[200,100],[100,100]]'
) ON CONFLICT DO NOTHING;

-- PARTNER-owned zone for d2 (same camera f101) — needed for partner↔partner isolation test
INSERT INTO zones (id, camera_id, owner_type, owner_partner_id, name, zone_type, coordinates)
VALUES (
  '00000000-0000-4000-8000-00000000e103',
  '00000000-0000-4000-8000-00000000f101',
  'PARTNER', '00000000-0000-4000-8000-0000000000d2',
  'Góndola Coca-Cola Z10', 'shelf', '[[200,0],[300,0],[300,100],[200,100]]'
) ON CONFLICT DO NOTHING;

-- Dwell session for TENANT zone (partner must NOT see this)
INSERT INTO zone_dwell_sessions (id, zone_id, person_id, entered_at, dwell_seconds)
VALUES (
  '00000000-0000-4000-8000-00000000ee01',
  '00000000-0000-4000-8000-00000000e101',
  'p001', '2026-07-20 08:00:00+00', 120
) ON CONFLICT DO NOTHING;

-- Dwell session for d1's zone (d1 can see; tenant a1 must also see)
INSERT INTO zone_dwell_sessions (id, zone_id, person_id, entered_at, dwell_seconds)
VALUES (
  '00000000-0000-4000-8000-00000000ee02',
  '00000000-0000-4000-8000-00000000e102',
  'p002', '2026-07-20 09:00:00+00', 60
) ON CONFLICT DO NOTHING;

-- Dwell session for d2's zone — d1 must NOT see this (partner↔partner isolation)
INSERT INTO zone_dwell_sessions (id, zone_id, person_id, entered_at, dwell_seconds)
VALUES (
  '00000000-0000-4000-8000-00000000ee03',
  '00000000-0000-4000-8000-00000000e103',
  'p005', '2026-07-20 10:00:00+00', 90
) ON CONFLICT DO NOTHING;

-- Tracking rows: 2 in Zona 10 (b1/f101), 2 in Zona 4 (b2/f102), 1 in Banco (b3/f103)
INSERT INTO tracking_coordinates ("time", camera_id, person_id, x, y)
VALUES
  ('2026-07-20 10:00:00+00', '00000000-0000-4000-8000-00000000f101', 'p001', 50,  50),
  ('2026-07-20 10:01:00+00', '00000000-0000-4000-8000-00000000f101', 'p001', 55,  52),
  ('2026-07-20 10:10:00+00', '00000000-0000-4000-8000-00000000f102', 'p003', 30,  40),
  ('2026-07-20 10:11:00+00', '00000000-0000-4000-8000-00000000f102', 'p003', 35,  42),
  ('2026-07-20 11:00:00+00', '00000000-0000-4000-8000-00000000f103', 'p004', 100, 100)
ON CONFLICT DO NOTHING;
