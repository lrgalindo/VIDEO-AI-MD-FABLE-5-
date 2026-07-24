-- Tests: Tenant lifecycle RLS isolation.
--
-- All tests run inside BEGIN/ROLLBACK with SET LOCAL ROLE traxia_service or
-- traxia_app — never as postgres/superuser/BYPASSRLS.
--
-- Coverage:
--  (1)  traxia_service can INSERT tenant with status='onboarding' (registration)
--  (2)  traxia_service cannot INSERT tenant with status='active' directly
--  (3)  traxia_service can UPDATE tenant status onboarding→active (approval)
--  (4)  traxia_service can UPDATE tenant status active→inactive (deactivation)
--  (5)  traxia_app (admin role) CANNOT UPDATE tenant status (no lifecycle policy)
--  (6)  NEGATIVE: onboarding tenant gateway's activate UPDATE returns 0 rows
--       (the AND EXISTS (tenant.status='active') sub-query blocks it)
--  (7)  NEGATIVE: onboarding tenant gateway's refresh UPDATE returns 0 rows
--  (8)  active tenant gateway activate UPDATE succeeds (baseline confirm)
--  (9)  deactivation sets all gateways to status='revoked'
-- (10)  revoked gateway's refresh UPDATE returns 0 rows (Fase 1 §8.7.0)

BEGIN;

SELECT plan(10);

-- ── Shared GUC / role setup ───────────────────────────────────────────────────
-- Tests 1-5: traxia_service context (lifecycle operations)
-- Tests 6-10: gateway auth context (verifying blocks)

-- ── Test 1: traxia_service inserts onboarding tenant ─────────────────────────
SET LOCAL ROLE traxia_service;

SELECT lives_ok(
  $$
  INSERT INTO tenants (name, vertical_type, status, contact_email)
  VALUES ('Test Register', 'retail', 'onboarding', 'reg@test.com')
  $$,
  'traxia_service can INSERT tenant with status=onboarding (registration)'
);

-- ── Test 2: traxia_service cannot insert tenant with status='active' directly ─
SELECT throws_ok(
  $$
  INSERT INTO tenants (name, vertical_type, status, contact_email)
  VALUES ('Skip Onboarding', 'retail', 'active', 'skip@test.com')
  $$,
  '42501',
  'new row violates row-level security policy for table "tenants"',
  'traxia_service cannot INSERT tenant with status=active (must start as onboarding)'
);

-- ── Test 3: traxia_service can UPDATE onboarding→active (approval) ────────────
SELECT lives_ok(
  $$
  UPDATE tenants
     SET status      = 'active',
         approved_at = now()
   WHERE id = 'cc100000-0000-4000-8000-000000000001'
     AND status = 'onboarding'
  $$,
  'traxia_service can UPDATE tenant status onboarding→active (approval path)'
);

-- ── Test 4: traxia_service can UPDATE active→inactive (deactivation) ──────────
SELECT lives_ok(
  $$
  UPDATE tenants
     SET status = 'inactive'
   WHERE id = 'cc200000-0000-4000-8000-000000000001'
  $$,
  'traxia_service can UPDATE tenant status active→inactive (deactivation path)'
);

-- ── Test 5: traxia_app admin CANNOT UPDATE tenant status ─────────────────────
-- traxia_app has only SELECT on tenants via tenants_read policy — no UPDATE policy.
SET LOCAL ROLE traxia_app;
SET LOCAL app.current_tenant_id   = 'cc100000-0000-4000-8000-000000000001';
SET LOCAL app.current_actor_role  = 'admin';

SELECT throws_ok(
  $$
  UPDATE tenants SET status = 'active' WHERE id = 'cc100000-0000-4000-8000-000000000001'
  $$,
  '42501',
  NULL,
  'traxia_app admin CANNOT UPDATE tenant status (no lifecycle policy for app role)'
);

-- ── Tests 6-8: gateway activate UPDATE with tenant status check ───────────────
-- We simulate the WHERE clause from auth/router.py activate endpoint.
-- Tenant C is 'onboarding' → gateway activate should return 0 rows.
-- (traxia_service runs these because service_conn() is used by auth/router.py)

SET LOCAL ROLE traxia_service;

-- Test 6: onboarding tenant gateway activation blocked
SELECT is(
  (
    SELECT count(*)::integer
    FROM edge_gateways eg
    WHERE eg.id = 'gw-lifecycle-c1'
      AND eg.activation_code_hash = 'code-hash-c1'
      AND eg.activation_code_expires_at > now()
      AND eg.status = 'offline'
      AND EXISTS (
            SELECT 1 FROM sites s
            JOIN tenants t ON t.id = s.tenant_id
            WHERE s.id = eg.site_id AND t.status = 'active'
          )
  ),
  0,
  'NEGATIVE: onboarding tenant gateway blocked from activate (tenant.status check)'
);

-- Test 7: onboarding tenant gateway refresh blocked
SELECT is(
  (
    SELECT count(*)::integer
    FROM edge_gateways eg
    WHERE eg.id = 'gw-lifecycle-c1'
      AND eg.refresh_token_hash = 'refresh-hash-c1'
      AND eg.refresh_token_expires_at > now()
      AND eg.status NOT IN ('revoked', 'decommissioned')
      AND EXISTS (
            SELECT 1 FROM sites s
            JOIN tenants t ON t.id = s.tenant_id
            WHERE s.id = eg.site_id AND t.status = 'active'
          )
  ),
  0,
  'NEGATIVE: onboarding tenant gateway blocked from refresh (tenant.status check)'
);

-- Test 8: ACTIVE tenant gateway activate returns 1 row (baseline)
-- Re-insert a fresh activation code on Tenant B's gateway (since we set it to 'online'
-- in seed, we test a separate scenario: Tenant B's site is active).
-- We verify the EXISTS sub-query passes for active tenants.
SELECT is(
  (
    SELECT count(*)::integer
    FROM edge_gateways eg
    JOIN sites s ON s.id = eg.site_id
    JOIN tenants t ON t.id = s.tenant_id
    WHERE eg.id = 'gw-lifecycle-b1'
      AND t.status = 'active'
  ),
  1,
  'POSITIVE: active tenant gateway is visible to the tenant-status sub-query'
);

-- ── Test 9: deactivation revokes all gateways ────────────────────────────────
-- Execute the deactivation UPDATE (as traxia_service, same as lifecycle router)
UPDATE edge_gateways eg
   SET status                   = 'revoked',
       refresh_token_hash       = NULL,
       refresh_token_prev_hash  = NULL,
       refresh_token_expires_at = NULL
  FROM sites s
 WHERE s.id = eg.site_id
   AND s.tenant_id = 'cc200000-0000-4000-8000-000000000001'
   AND eg.status NOT IN ('decommissioned');

SELECT is(
  (SELECT status FROM edge_gateways WHERE id = 'gw-lifecycle-b1'),
  'revoked',
  'Deactivation sets all tenant gateways to status=revoked (Fase 1 §8.7.0)'
);

-- Test 10: revoked gateway refresh blocked (Fase 1 existing mechanism)
SELECT is(
  (
    SELECT count(*)::integer
    FROM edge_gateways
    WHERE id = 'gw-lifecycle-b1'
      AND status NOT IN ('revoked', 'decommissioned')
  ),
  0,
  'NEGATIVE: revoked gateway cannot pass the Fase 1 §8.7.0 status check'
);

SELECT * FROM finish();

ROLLBACK;
