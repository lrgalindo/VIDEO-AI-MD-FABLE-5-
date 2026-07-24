-- Seed data for lifecycle RLS and API tests.
-- Self-contained: uses ON CONFLICT DO NOTHING so it is safe to re-run.

-- Platform admin (SuperAdmin) for lifecycle tests
INSERT INTO platform_admins (id, email, status) VALUES
  ('cc000000-0000-4000-8000-000000000001', 'superadmin@traxia-test.com', 'active')
ON CONFLICT DO NOTHING;

-- Reseller for lifecycle tests
INSERT INTO resellers (id, name, status) VALUES
  ('cc000000-0000-4000-8000-000000000010', 'Reseller Lifecycle Test', 'active')
ON CONFLICT DO NOTHING;

-- Tenant A: already 'onboarding' (default) — for approval tests
INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) VALUES
  ('cc100000-0000-4000-8000-000000000001',
   'cc000000-0000-4000-8000-000000000010',
   'Tenant Onboarding A', 'retail', 'onboarding', 'contact@tenant-a.com')
ON CONFLICT DO NOTHING;

-- Tenant B: already 'active' — for deactivation tests
INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) VALUES
  ('cc200000-0000-4000-8000-000000000001',
   'cc000000-0000-4000-8000-000000000010',
   'Tenant Active B', 'retail', 'active', 'contact@tenant-b.com')
ON CONFLICT DO NOTHING;

-- Site + Gateway for Tenant B (to be revoked on deactivation)
INSERT INTO sites (id, tenant_id, name, status) VALUES
  ('cc200000-0000-4000-8000-000000000002',
   'cc200000-0000-4000-8000-000000000001',
   'Site B-1', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO edge_gateways (id, site_id, vertical_type, status,
                            refresh_token_hash, refresh_token_expires_at) VALUES
  ('gw-lifecycle-b1',
   'cc200000-0000-4000-8000-000000000002',
   'retail', 'online',
   'somehash-b1', now() + interval '90 days')
ON CONFLICT DO NOTHING;

-- Tenant C: 'onboarding' — has a gateway with activation code, for the negative auth test
INSERT INTO tenants (id, reseller_id, name, vertical_type, status, contact_email) VALUES
  ('cc300000-0000-4000-8000-000000000001',
   'cc000000-0000-4000-8000-000000000010',
   'Tenant Onboarding C', 'retail', 'onboarding', 'contact@tenant-c.com')
ON CONFLICT DO NOTHING;

INSERT INTO sites (id, tenant_id, name, status) VALUES
  ('cc300000-0000-4000-8000-000000000002',
   'cc300000-0000-4000-8000-000000000001',
   'Site C-1', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO edge_gateways (id, site_id, vertical_type, status,
                            activation_code_hash, activation_code_expires_at,
                            refresh_token_hash, refresh_token_expires_at) VALUES
  ('gw-lifecycle-c1',
   'cc300000-0000-4000-8000-000000000002',
   'retail', 'offline',
   'code-hash-c1', now() + interval '72 hours',
   'refresh-hash-c1', now() + interval '90 days')
ON CONFLICT DO NOTHING;
