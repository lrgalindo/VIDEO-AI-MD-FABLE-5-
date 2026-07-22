-- Seed data for backoffice RLS and API tests.
-- Self-contained: uses ON CONFLICT DO NOTHING so it is safe to re-run.

-- Reseller
INSERT INTO resellers (id, name) VALUES
  ('bb000000-0000-4000-8000-000000000001', 'Reseller Backoffice Test')
ON CONFLICT DO NOTHING;

-- Tenant A (the "admin" tenant in these tests)
INSERT INTO tenants (id, reseller_id, name, vertical_type, status) VALUES
  ('bb100000-0000-4000-8000-000000000001',
   'bb000000-0000-4000-8000-000000000001', 'Tenant Backoffice A', 'retail', 'active')
ON CONFLICT DO NOTHING;

-- Tenant B (cross-tenant isolation target)
INSERT INTO tenants (id, reseller_id, name, vertical_type, status) VALUES
  ('bb200000-0000-4000-8000-000000000001',
   'bb000000-0000-4000-8000-000000000001', 'Tenant Backoffice B', 'retail', 'active')
ON CONFLICT DO NOTHING;

-- Two sites for Tenant A
INSERT INTO sites (id, tenant_id, name, status) VALUES
  ('bb100000-0000-4000-8000-000000000002',
   'bb100000-0000-4000-8000-000000000001', 'Site A-1', 'active'),
  ('bb100000-0000-4000-8000-000000000003',
   'bb100000-0000-4000-8000-000000000001', 'Site A-2', 'active')
ON CONFLICT DO NOTHING;

-- One site for Tenant B (cross-tenant)
INSERT INTO sites (id, tenant_id, name, status) VALUES
  ('bb200000-0000-4000-8000-000000000002',
   'bb200000-0000-4000-8000-000000000001', 'Site B-1', 'active')
ON CONFLICT DO NOTHING;

-- Camera on Site A-1 (for zone tests)
INSERT INTO cameras (id, site_id, name, rtsp_url_ciphertext, rtsp_url_key_id, status) VALUES
  ('bb100000-0000-4000-8000-000000000004',
   'bb100000-0000-4000-8000-000000000002', 'Cam A-1',
   decode('6741414141414271594251683734674b484f766b50626f3078313433307857334a6a445f4c44776d36434658324c63587639446d6e437372556c37695554634233365763666d694d674d4178516e4377464d4e66357373436a6545714662564f483356564c4c4c575964485639515f4d2d356a744c49673d', 'hex'),
   'test-key-v1', 'active')
ON CONFLICT DO NOTHING;

-- Admin user for Tenant A
INSERT INTO users (id, tenant_id, email, role, status) VALUES
  ('bb100000-0000-4000-8000-000000000010',
   'bb100000-0000-4000-8000-000000000001', 'admin@backoffice-test.com', 'admin', 'active')
ON CONFLICT DO NOTHING;
