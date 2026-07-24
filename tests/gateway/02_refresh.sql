-- Test (b): successful token refresh.
-- Verifies the SDD §8.7.0 UPDATE pattern returns 1 row for a gateway that is
-- online, has the correct hash, and has a non-expired token.
BEGIN;
SET LOCAL ROLE traxia_service;
SELECT plan(1);

WITH result AS (
  UPDATE edge_gateways
     SET refresh_token_hash       = encode(digest('rotated-refresh-token', 'sha256'), 'hex'),
         refresh_token_expires_at = now() + interval '90 days',
         last_token_refresh_at    = now()
   WHERE id                       = 'gw-test-refresh-001'
     AND refresh_token_hash       = encode(digest('valid-refresh-token', 'sha256'), 'hex')
     AND refresh_token_expires_at > now()
     AND status NOT IN ('revoked', 'decommissioned')
  RETURNING id
)
SELECT is(
  (SELECT count(*)::int FROM result),
  1,
  'Refresh succeeds: active gateway with valid hash returns 1 row and rotates the token'
);

SELECT * FROM finish();
ROLLBACK;
