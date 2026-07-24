-- Test: activation code is single-use.
-- The first call clears activation_code_hash atomically (sets it to NULL).
-- A second call with the same code finds NULL != hash → returns 0 rows.
-- Both statements run in the same transaction so the second sees the NULL written by the first.
BEGIN;
SET LOCAL ROLE traxia_service;
SELECT plan(2);

-- First exchange: must succeed.
WITH result AS (
  UPDATE edge_gateways
     SET activation_code_hash       = NULL,
         activation_code_expires_at = NULL,
         refresh_token_hash         = encode(digest('activation-reuse-first-refresh', 'sha256'), 'hex'),
         refresh_token_expires_at   = now() + interval '90 days',
         last_token_refresh_at      = now(),
         status                     = 'online'
   WHERE id                         = 'gw-test-activate-reuse-001'
     AND activation_code_hash       = encode(digest('test-activate-reuse-code', 'sha256'), 'hex')
     AND activation_code_expires_at > now()
     AND status                     = 'offline'
  RETURNING id
)
SELECT is(
  (SELECT count(*)::int FROM result),
  1,
  'First activation succeeds: valid one-time code returns 1 row'
);

-- Second exchange with the SAME code: must fail.
-- The first UPDATE already set activation_code_hash = NULL, so this WHERE clause
-- finds no matching row.
WITH result AS (
  UPDATE edge_gateways
     SET activation_code_hash       = NULL,
         activation_code_expires_at = NULL,
         refresh_token_hash         = encode(digest('activation-reuse-second-refresh', 'sha256'), 'hex'),
         refresh_token_expires_at   = now() + interval '90 days',
         last_token_refresh_at      = now(),
         status                     = 'online'
   WHERE id                         = 'gw-test-activate-reuse-001'
     AND activation_code_hash       = encode(digest('test-activate-reuse-code', 'sha256'), 'hex')
     AND activation_code_expires_at > now()
     AND status                     = 'offline'
  RETURNING id
)
SELECT is(
  (SELECT count(*)::int FROM result),
  0,
  'Second activation with same code fails: activation_code_hash already cleared'
);

SELECT * FROM finish();
ROLLBACK;
