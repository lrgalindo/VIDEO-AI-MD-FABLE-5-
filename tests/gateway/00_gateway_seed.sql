-- Seed data for gateway auth tests (§8.7.0).
-- Self-contained: inserts its own reseller/tenant/site with ON CONFLICT DO NOTHING
-- so it is safe to run after or independently of the isolation test seed.

INSERT INTO resellers (id, name) VALUES
  ('00000000-0000-4000-8000-0000000000e1', 'Reseller Demo Centroamérica')
ON CONFLICT DO NOTHING;

INSERT INTO tenants (id, reseller_id, name, vertical_type, status) VALUES
  ('00000000-0000-4000-8000-0000000000a1',
   '00000000-0000-4000-8000-0000000000e1', 'La Torre (retail demo)', 'retail', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO sites (id, tenant_id, name, status) VALUES
  ('00000000-0000-4000-8000-0000000000b1',
   '00000000-0000-4000-8000-0000000000a1', 'La Torre Zona 10', 'active')
ON CONFLICT DO NOTHING;

-- gw-test-activate-001: pending activation — has a valid one-time activation code.
-- ON CONFLICT DO UPDATE refreshes the activation expiry so the seed is safe to
-- re-run on a long-lived dev database without stale expirations.
INSERT INTO edge_gateways (id, site_id, vertical_type, status,
                           activation_code_hash, activation_code_expires_at)
VALUES (
  'gw-test-activate-001',
  '00000000-0000-4000-8000-0000000000b1',
  'retail', 'offline',
  encode(digest('test-activate-code', 'sha256'), 'hex'),
  now() + interval '1 hour'
) ON CONFLICT (id) DO UPDATE
  SET activation_code_hash       = encode(digest('test-activate-code', 'sha256'), 'hex'),
      activation_code_expires_at = now() + interval '1 hour',
      status                     = 'offline';

-- gw-test-refresh-001: active gateway with a valid refresh token.
INSERT INTO edge_gateways (id, site_id, vertical_type, status,
                           refresh_token_hash, refresh_token_expires_at)
VALUES (
  'gw-test-refresh-001',
  '00000000-0000-4000-8000-0000000000b1',
  'retail', 'online',
  encode(digest('valid-refresh-token', 'sha256'), 'hex'),
  now() + interval '90 days'
) ON CONFLICT DO NOTHING;

-- gw-test-revoked-001: valid hash and expiry, but status='revoked' — refresh must fail.
INSERT INTO edge_gateways (id, site_id, vertical_type, status,
                           refresh_token_hash, refresh_token_expires_at)
VALUES (
  'gw-test-revoked-001',
  '00000000-0000-4000-8000-0000000000b1',
  'retail', 'revoked',
  encode(digest('revoked-gw-token', 'sha256'), 'hex'),
  now() + interval '90 days'
) ON CONFLICT DO NOTHING;

-- gw-test-expired-001: valid hash, correct status, but refresh_token_expires_at is in the past.
INSERT INTO edge_gateways (id, site_id, vertical_type, status,
                           refresh_token_hash, refresh_token_expires_at)
VALUES (
  'gw-test-expired-001',
  '00000000-0000-4000-8000-0000000000b1',
  'retail', 'online',
  encode(digest('expired-gw-token', 'sha256'), 'hex'),
  now() - interval '1 second'
) ON CONFLICT DO NOTHING;

-- gw-test-reuse-001: used to verify the one-time-use property —
-- first refresh succeeds (rotates the hash), second attempt with the old hash fails.
INSERT INTO edge_gateways (id, site_id, vertical_type, status,
                           refresh_token_hash, refresh_token_expires_at)
VALUES (
  'gw-test-reuse-001',
  '00000000-0000-4000-8000-0000000000b1',
  'retail', 'online',
  encode(digest('reuse-original-token', 'sha256'), 'hex'),
  now() + interval '90 days'
) ON CONFLICT DO NOTHING;

-- gw-test-activate-reuse-001: second gateway for the activation-code-reuse test.
-- Has a valid activation code that must work exactly once.
INSERT INTO edge_gateways (id, site_id, vertical_type, status,
                           activation_code_hash, activation_code_expires_at)
VALUES (
  'gw-test-activate-reuse-001',
  '00000000-0000-4000-8000-0000000000b1',
  'retail', 'offline',
  encode(digest('test-activate-reuse-code', 'sha256'), 'hex'),
  now() + interval '1 hour'
) ON CONFLICT (id) DO UPDATE
  SET activation_code_hash       = encode(digest('test-activate-reuse-code', 'sha256'), 'hex'),
      activation_code_expires_at = now() + interval '1 hour',
      status                     = 'offline';

-- gw-test-grace-001: gateway for the lost-response / grace-window test.
INSERT INTO edge_gateways (id, site_id, vertical_type, status,
                           refresh_token_hash, refresh_token_expires_at)
VALUES (
  'gw-test-grace-001',
  '00000000-0000-4000-8000-0000000000b1',
  'retail', 'online',
  encode(digest('grace-original-token', 'sha256'), 'hex'),
  now() + interval '90 days'
) ON CONFLICT DO NOTHING;
