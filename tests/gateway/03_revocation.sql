-- Test (c): refresh rejected after revocation.
-- gw-test-revoked-001 has a valid hash and non-expired token, but status='revoked'.
-- The status NOT IN ('revoked','decommissioned') clause must block the UPDATE.
BEGIN;
SET LOCAL ROLE traxia_service;
SELECT plan(1);

WITH result AS (
  UPDATE edge_gateways
     SET refresh_token_hash       = encode(digest('any-new-token', 'sha256'), 'hex'),
         refresh_token_expires_at = now() + interval '90 days',
         last_token_refresh_at    = now()
   WHERE id                       = 'gw-test-revoked-001'
     AND refresh_token_hash       = encode(digest('revoked-gw-token', 'sha256'), 'hex')
     AND refresh_token_expires_at > now()
     AND status NOT IN ('revoked', 'decommissioned')
  RETURNING id
)
SELECT is(
  (SELECT count(*)::int FROM result),
  0,
  'Refresh rejected: status=''revoked'' blocks the UPDATE even with a valid, non-expired hash'
);

SELECT * FROM finish();
ROLLBACK;
