-- Test (a): successful activation.
-- The activation UPDATE clears the one-time code and writes the refresh_token_hash.
-- Runs as traxia_service (not superuser) to enforce the same RLS policies the API uses.
BEGIN;
SET LOCAL ROLE traxia_service;
SELECT plan(2);

-- Pre-condition: activation_code_hash is set before we run the activation.
SELECT is(
  (SELECT activation_code_hash
     FROM edge_gateways
    WHERE id = 'gw-test-activate-001'),
  encode(digest('test-activate-code', 'sha256'), 'hex'),
  'Pre-condition: gateway has the expected activation_code_hash'
);

-- Activation UPDATE: atomically verifies code hash + expiry + offline status,
-- clears the code, writes refresh_token_hash, and sets status = ''online''.
WITH result AS (
  UPDATE edge_gateways
     SET activation_code_hash       = NULL,
         activation_code_expires_at = NULL,
         refresh_token_hash         = encode(digest('new-refresh-from-activate', 'sha256'), 'hex'),
         refresh_token_expires_at   = now() + interval '90 days',
         last_token_refresh_at      = now(),
         status                     = 'online'
   WHERE id                         = 'gw-test-activate-001'
     AND activation_code_hash       = encode(digest('test-activate-code', 'sha256'), 'hex')
     AND activation_code_expires_at > now()
     AND status                     = 'offline'
  RETURNING id
)
SELECT is(
  (SELECT count(*)::int FROM result),
  1,
  'Activation succeeds: valid one-time code exchanges for a session (1 row returned)'
);

SELECT * FROM finish();
ROLLBACK;
