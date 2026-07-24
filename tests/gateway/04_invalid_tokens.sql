-- Test (d): refresh rejected for expired, wrong, or already-used tokens.
-- Three sub-cases in one file, each a separate assertion.
-- Important: all three run in the SAME BEGIN/ROLLBACK so changes within the
-- transaction are visible to later statements — which is exactly how we prove
-- the one-time-use property (already-used sub-case).
BEGIN;
SET LOCAL ROLE traxia_service;
SELECT plan(3);

-- Case 1: expired token — refresh_token_expires_at is in the past.
WITH result AS (
  UPDATE edge_gateways
     SET refresh_token_hash       = encode(digest('any-new-token', 'sha256'), 'hex'),
         refresh_token_expires_at = now() + interval '90 days',
         last_token_refresh_at    = now()
   WHERE id                       = 'gw-test-expired-001'
     AND refresh_token_hash       = encode(digest('expired-gw-token', 'sha256'), 'hex')
     AND refresh_token_expires_at > now()
     AND status NOT IN ('revoked', 'decommissioned')
  RETURNING id
)
SELECT is(
  (SELECT count(*)::int FROM result),
  0,
  'Refresh rejected: token whose refresh_token_expires_at is in the past'
);

-- Case 2: wrong hash — correct gateway and status, but the presented token does not match.
WITH result AS (
  UPDATE edge_gateways
     SET refresh_token_hash       = encode(digest('any-new-token', 'sha256'), 'hex'),
         refresh_token_expires_at = now() + interval '90 days',
         last_token_refresh_at    = now()
   WHERE id                       = 'gw-test-refresh-001'
     AND refresh_token_hash       = encode(digest('COMPLETELY-WRONG-TOKEN', 'sha256'), 'hex')
     AND refresh_token_expires_at > now()
     AND status NOT IN ('revoked', 'decommissioned')
  RETURNING id
)
SELECT is(
  (SELECT count(*)::int FROM result),
  0,
  'Refresh rejected: wrong/invalid token hash does not match stored hash'
);

-- Case 3: already-used token — proves the one-time-use property of refresh tokens.
-- Step A: first refresh succeeds and rotates gw-test-reuse-001 to a new hash.
UPDATE edge_gateways
   SET refresh_token_hash       = encode(digest('rotated-reuse-token', 'sha256'), 'hex'),
       refresh_token_expires_at = now() + interval '90 days',
       last_token_refresh_at    = now()
 WHERE id                       = 'gw-test-reuse-001'
   AND refresh_token_hash       = encode(digest('reuse-original-token', 'sha256'), 'hex')
   AND refresh_token_expires_at > now()
   AND status NOT IN ('revoked', 'decommissioned');

-- Step B: attempt to reuse the OLD token — the hash no longer matches because Step A
-- already rotated it. This statement runs after Step A in the same transaction, so it
-- sees the updated state (refresh_token_hash now points to 'rotated-reuse-token').
WITH result AS (
  UPDATE edge_gateways
     SET refresh_token_hash       = encode(digest('any-another-token', 'sha256'), 'hex'),
         refresh_token_expires_at = now() + interval '90 days',
         last_token_refresh_at    = now()
   WHERE id                       = 'gw-test-reuse-001'
     AND refresh_token_hash       = encode(digest('reuse-original-token', 'sha256'), 'hex')
     AND refresh_token_expires_at > now()
     AND status NOT IN ('revoked', 'decommissioned')
  RETURNING id
)
SELECT is(
  (SELECT count(*)::int FROM result),
  0,
  'Refresh rejected: already-used token hash no longer matches after first successful rotation'
);

SELECT * FROM finish();
ROLLBACK;
