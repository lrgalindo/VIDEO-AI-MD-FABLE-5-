-- Test: lost-response grace window (§8.7.0 mitigation).
--
-- Scenario: backend rotates the hash (step 1) but the HTTP response is lost.
-- The gateway retries with its old token (step 2) — must succeed.
-- A replay attempt with the same old token after the retry (step 3) must fail
-- because the prev_hash slot was consumed in step 2.
--
-- All three steps run in one BEGIN/ROLLBACK so each UPDATE sees the state left
-- by the previous one — exactly the same visibility a real API server would have.
BEGIN;
SET LOCAL ROLE traxia_service;
SELECT plan(3);

-- Step 1: normal rotation — simulate the backend completing a refresh.
-- Backend stores 'grace-rotated-token' as the new hash and saves
-- 'grace-original-token' in prev_hash for the grace window.
WITH result AS (
  UPDATE edge_gateways
     SET refresh_token_hash            = encode(digest('grace-rotated-token', 'sha256'), 'hex'),
         refresh_token_expires_at      = now() + interval '90 days',
         last_token_refresh_at         = now(),
         refresh_token_prev_hash       = CASE
             WHEN refresh_token_prev_hash = encode(digest('grace-original-token', 'sha256'), 'hex') THEN NULL
             ELSE encode(digest('grace-original-token', 'sha256'), 'hex')
           END,
         refresh_token_prev_expires_at = CASE
             WHEN refresh_token_prev_hash = encode(digest('grace-original-token', 'sha256'), 'hex') THEN NULL
             ELSE now() + interval '90 seconds'
           END
   WHERE id                            = 'gw-test-grace-001'
     AND (
           refresh_token_hash          = encode(digest('grace-original-token', 'sha256'), 'hex')
       OR (refresh_token_prev_hash     = encode(digest('grace-original-token', 'sha256'), 'hex')
           AND refresh_token_prev_expires_at > now())
     )
     AND refresh_token_expires_at      > now()
     AND status NOT IN ('revoked', 'decommissioned')
  RETURNING id
)
SELECT is(
  (SELECT count(*)::int FROM result),
  1,
  'Step 1 (normal rotation): current hash matches, returns 1 row'
);

-- Step 2: gateway retries with its old token (response was lost).
-- 'grace-original-token' is now in prev_hash within the grace window.
-- This must succeed and clear prev_hash so the old token cannot be reused again.
WITH result AS (
  UPDATE edge_gateways
     SET refresh_token_hash            = encode(digest('grace-final-token', 'sha256'), 'hex'),
         refresh_token_expires_at      = now() + interval '90 days',
         last_token_refresh_at         = now(),
         refresh_token_prev_hash       = CASE
             WHEN refresh_token_prev_hash = encode(digest('grace-original-token', 'sha256'), 'hex') THEN NULL
             ELSE encode(digest('grace-original-token', 'sha256'), 'hex')
           END,
         refresh_token_prev_expires_at = CASE
             WHEN refresh_token_prev_hash = encode(digest('grace-original-token', 'sha256'), 'hex') THEN NULL
             ELSE now() + interval '90 seconds'
           END
   WHERE id                            = 'gw-test-grace-001'
     AND (
           refresh_token_hash          = encode(digest('grace-original-token', 'sha256'), 'hex')
       OR (refresh_token_prev_hash     = encode(digest('grace-original-token', 'sha256'), 'hex')
           AND refresh_token_prev_expires_at > now())
     )
     AND refresh_token_expires_at      > now()
     AND status NOT IN ('revoked', 'decommissioned')
  RETURNING id
)
SELECT is(
  (SELECT count(*)::int FROM result),
  1,
  'Step 2 (grace retry): old token matches via prev_hash, returns 1 row — lost response recovered'
);

-- Step 3: replay attempt with the same old token must fail.
-- prev_hash was cleared in step 2 (consumed). current hash is now 'grace-final-token'.
-- Neither slot matches 'grace-original-token' anymore.
WITH result AS (
  UPDATE edge_gateways
     SET refresh_token_hash            = encode(digest('grace-replay-token', 'sha256'), 'hex'),
         refresh_token_expires_at      = now() + interval '90 days',
         last_token_refresh_at         = now(),
         refresh_token_prev_hash       = CASE
             WHEN refresh_token_prev_hash = encode(digest('grace-original-token', 'sha256'), 'hex') THEN NULL
             ELSE encode(digest('grace-original-token', 'sha256'), 'hex')
           END,
         refresh_token_prev_expires_at = CASE
             WHEN refresh_token_prev_hash = encode(digest('grace-original-token', 'sha256'), 'hex') THEN NULL
             ELSE now() + interval '90 seconds'
           END
   WHERE id                            = 'gw-test-grace-001'
     AND (
           refresh_token_hash          = encode(digest('grace-original-token', 'sha256'), 'hex')
       OR (refresh_token_prev_hash     = encode(digest('grace-original-token', 'sha256'), 'hex')
           AND refresh_token_prev_expires_at > now())
     )
     AND refresh_token_expires_at      > now()
     AND status NOT IN ('revoked', 'decommissioned')
  RETURNING id
)
SELECT is(
  (SELECT count(*)::int FROM result),
  0,
  'Step 3 (replay blocked): prev_hash consumed in step 2, same old token rejected'
);

SELECT * FROM finish();
ROLLBACK;
