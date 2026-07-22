-- Seed data for Motor de Acciones RLS and API tests.
-- Self-contained via ON CONFLICT DO NOTHING.

-- Reseller
INSERT INTO resellers (id, name, status) VALUES
  ('ac000000-0000-4000-8000-000000000010', 'Reseller Actions Test', 'active')
ON CONFLICT DO NOTHING;

-- Tenant A (for positive tests and cross-tenant negative test)
INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) VALUES
  ('ac100000-0000-4000-8000-000000000001',
   'ac000000-0000-4000-8000-000000000010',
   'Tenant Actions A', 'retail', 'active', 'contact@tenant-a-actions.com')
ON CONFLICT DO NOTHING;

-- Tenant B (for cross-tenant isolation test — Tenant A must never see B's data)
INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) VALUES
  ('ac200000-0000-4000-8000-000000000001',
   'ac000000-0000-4000-8000-000000000010',
   'Tenant Actions B', 'retail', 'active', 'contact@tenant-b-actions.com')
ON CONFLICT DO NOTHING;

-- Sites
INSERT INTO sites (id, tenant_id, name, status) VALUES
  ('ac100000-0000-4000-8000-000000000002',
   'ac100000-0000-4000-8000-000000000001', 'Site A-1', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO sites (id, tenant_id, name, status) VALUES
  ('ac200000-0000-4000-8000-000000000002',
   'ac200000-0000-4000-8000-000000000001', 'Site B-1', 'active')
ON CONFLICT DO NOTHING;

-- Cameras for each site (needed for zone references and tracking_coordinates)
INSERT INTO cameras (id, site_id, name, rtsp_url_ciphertext, rtsp_url_key_id, status) VALUES
  ('ac100000-0000-4000-8000-000000000003',
   'ac100000-0000-4000-8000-000000000002', 'Cam A-1',
   decode('6741414141414271594251683734674b484f766b50626f3078313433307857334a6a445f4c44776d36434658324c63587639446d6e437372556c37695554634233365763666d694d674d4178516e4377464d4e66357373436a6545714662564f483356564c4c4c575964485639515f4d2d356a744c49673d', 'hex'),
   'test-key-v1', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO cameras (id, site_id, name, rtsp_url_ciphertext, rtsp_url_key_id, status) VALUES
  ('ac200000-0000-4000-8000-000000000003',
   'ac200000-0000-4000-8000-000000000002', 'Cam B-1',
   decode('6741414141414271594251685472304743716e756a33374c3671466e6146447a4f674d5931314632345a695233376c397a6a4533485078727a6945344a466337524b33744145314e6c656a4143506a5a5f6d7849475962643076634f2d6652665444565a4f576a5557735f765f4c345a6d373573554c343d', 'hex'),
   'test-key-v1', 'active')
ON CONFLICT DO NOTHING;

-- Zones: Tenant A checkout zone (for SOP rules)
INSERT INTO zones
    (id, camera_id, name, zone_type, coordinates,
     owner_type, owner_tenant_id, owner_partner_id) VALUES
  ('ac100000-0000-4000-8000-000000000004',
   'ac100000-0000-4000-8000-000000000003',
   'Checkout Zone A', 'staff_exclusion',
   '[[0,0],[100,0],[100,100],[0,100]]',
   'TENANT', 'ac100000-0000-4000-8000-000000000001', NULL)
ON CONFLICT DO NOTHING;

-- Zones: Tenant B zone (must NOT be reachable from Tenant A's context)
INSERT INTO zones
    (id, camera_id, name, zone_type, coordinates,
     owner_type, owner_tenant_id, owner_partner_id) VALUES
  ('ac200000-0000-4000-8000-000000000004',
   'ac200000-0000-4000-8000-000000000003',
   'Checkout Zone B', 'staff_exclusion',
   '[[0,0],[100,0],[100,100],[0,100]]',
   'TENANT', 'ac200000-0000-4000-8000-000000000001', NULL)
ON CONFLICT DO NOTHING;

-- Users (admin for each tenant, for API tests)
INSERT INTO users (id, tenant_id, email, role, status) VALUES
  ('ac100000-0000-4000-8000-000000000005',
   'ac100000-0000-4000-8000-000000000001', 'admin@tenant-a-actions.com', 'admin', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO users (id, tenant_id, email, role, status) VALUES
  ('ac200000-0000-4000-8000-000000000005',
   'ac200000-0000-4000-8000-000000000001', 'admin@tenant-b-actions.com', 'admin', 'active')
ON CONFLICT DO NOTHING;

-- Action rules: Tenant A rule on Zone A (positive case)
INSERT INTO action_rules
    (id, tenant_id, site_id, zone_id, name, rule_type,
     threshold_value, threshold_window_minutes, enabled) VALUES
  ('ac100000-0000-4000-8000-000000000006',
   'ac100000-0000-4000-8000-000000000001',
   'ac100000-0000-4000-8000-000000000002',
   'ac100000-0000-4000-8000-000000000004',
   'Queue Alert A', 'threshold', 5, 10, TRUE)
ON CONFLICT DO NOTHING;

-- Action rules: Tenant B rule on Zone B
INSERT INTO action_rules
    (id, tenant_id, site_id, zone_id, name, rule_type,
     threshold_value, threshold_window_minutes, enabled) VALUES
  ('ac200000-0000-4000-8000-000000000006',
   'ac200000-0000-4000-8000-000000000001',
   'ac200000-0000-4000-8000-000000000002',
   'ac200000-0000-4000-8000-000000000004',
   'Queue Alert B', 'threshold', 5, 10, TRUE)
ON CONFLICT DO NOTHING;

-- Action channels: Tenant A Slack channel
INSERT INTO action_channels
    (id, tenant_id, name, channel_type, config_json, enabled) VALUES
  ('ac100000-0000-4000-8000-000000000007',
   'ac100000-0000-4000-8000-000000000001',
   'Slack Alert A', 'slack',
   '{"webhook_url": "https://hooks.slack.com/test-a"}', TRUE)
ON CONFLICT DO NOTHING;

-- Action channels: Tenant B Slack channel
INSERT INTO action_channels
    (id, tenant_id, name, channel_type, config_json, enabled) VALUES
  ('ac200000-0000-4000-8000-000000000007',
   'ac200000-0000-4000-8000-000000000001',
   'Slack Alert B', 'slack',
   '{"webhook_url": "https://hooks.slack.com/test-b"}', TRUE)
ON CONFLICT DO NOTHING;

-- Dwell sessions: Tenant B has 10 people stuck in Zone B (simulates triggered condition)
-- This data must NEVER be visible from Tenant A's evaluation context.
INSERT INTO zone_dwell_sessions (zone_id, person_id, entered_at) VALUES
  ('ac200000-0000-4000-8000-000000000004', 'person-b-001', now() - interval '20 minutes'),
  ('ac200000-0000-4000-8000-000000000004', 'person-b-002', now() - interval '20 minutes'),
  ('ac200000-0000-4000-8000-000000000004', 'person-b-003', now() - interval '20 minutes'),
  ('ac200000-0000-4000-8000-000000000004', 'person-b-004', now() - interval '20 minutes'),
  ('ac200000-0000-4000-8000-000000000004', 'person-b-005', now() - interval '20 minutes'),
  ('ac200000-0000-4000-8000-000000000004', 'person-b-006', now() - interval '20 minutes'),
  ('ac200000-0000-4000-8000-000000000004', 'person-b-007', now() - interval '20 minutes'),
  ('ac200000-0000-4000-8000-000000000004', 'person-b-008', now() - interval '20 minutes'),
  ('ac200000-0000-4000-8000-000000000004', 'person-b-009', now() - interval '20 minutes'),
  ('ac200000-0000-4000-8000-000000000004', 'person-b-010', now() - interval '20 minutes')
ON CONFLICT DO NOTHING;
