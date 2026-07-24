-- RLS isolation tests for Motor de Acciones tables.
-- All tests run inside BEGIN/ROLLBACK — no persistent state.
-- Never runs as superuser/BYPASSRLS; uses SET LOCAL ROLE only.
--
-- Coverage:
--  (1)  traxia_app admin A can SELECT action_rules for Tenant A
--  (2)  traxia_app admin A cannot SELECT action_rules for Tenant B
--  (3)  traxia_app admin A can INSERT action_rule for Tenant A
--  (4)  traxia_app admin A cannot INSERT action_rule for Tenant B
--  (5)  traxia_app admin A can SELECT action_channels for Tenant A
--  (6)  traxia_app admin A cannot SELECT action_channels for Tenant B
--  (7)  traxia_app operator can SELECT (read-only) action_rules for own tenant
--  (8)  traxia_app operator cannot INSERT action_rules (admin only)
--  (9)  action_log reads scoped to tenant
-- (10)  NEGATIVE (critical): Tenant A rule evaluated with Zone B zone_id
--       returns zero rows from zone_dwell_sessions — even with 10 active sessions
--       in Zone B — because zone.owner_tenant_id != Tenant A

BEGIN;

SELECT plan(10);

-- ── Test 1: Admin A sees own rules ───────────────────────────────────────────
SET LOCAL ROLE traxia_app;
SET LOCAL app.current_tenant_id  = 'ac100000-0000-4000-8000-000000000001';
SET LOCAL app.current_actor_role = 'admin';
SET LOCAL app.current_user_id    = 'ac100000-0000-4000-8000-000000000005';

SELECT is(
  (SELECT count(*)::integer FROM action_rules
   WHERE tenant_id = 'ac100000-0000-4000-8000-000000000001'::uuid),
  1,
  'Admin A can see own action_rules (count=1)'
);

-- ── Test 2: Admin A CANNOT see Tenant B rules ────────────────────────────────
SELECT is(
  (SELECT count(*)::integer FROM action_rules
   WHERE tenant_id = 'ac200000-0000-4000-8000-000000000001'::uuid),
  0,
  'Admin A cannot see Tenant B action_rules (cross-tenant blocked)'
);

-- ── Test 3: Admin A can INSERT rule for own tenant ───────────────────────────
SELECT lives_ok(
  $$
  INSERT INTO action_rules
      (tenant_id, name, rule_type, threshold_value, threshold_window_minutes)
  VALUES
      ('ac100000-0000-4000-8000-000000000001',
       'Test Rule Insert A', 'threshold', 3, 5)
  $$,
  'Admin A can INSERT action_rule for own tenant'
);

-- ── Test 4: Admin A CANNOT INSERT rule for Tenant B ──────────────────────────
SELECT throws_ok(
  $$
  INSERT INTO action_rules
      (tenant_id, name, rule_type, threshold_value, threshold_window_minutes)
  VALUES
      ('ac200000-0000-4000-8000-000000000001',
       'Cross-Tenant Rule', 'threshold', 3, 5)
  $$,
  '42501',
  NULL,
  'Admin A cannot INSERT action_rule for Tenant B (RLS blocks cross-tenant write)'
);

-- ── Test 5: Admin A sees own channels ────────────────────────────────────────
SELECT is(
  (SELECT count(*)::integer FROM action_channels
   WHERE tenant_id = 'ac100000-0000-4000-8000-000000000001'::uuid),
  1,
  'Admin A can see own action_channels'
);

-- ── Test 6: Admin A CANNOT see Tenant B channels ─────────────────────────────
SELECT is(
  (SELECT count(*)::integer FROM action_channels
   WHERE tenant_id = 'ac200000-0000-4000-8000-000000000001'::uuid),
  0,
  'Admin A cannot see Tenant B action_channels'
);

-- ── Test 7: Operator can SELECT rules ────────────────────────────────────────
SET LOCAL app.current_actor_role = 'operator';
SET LOCAL app.current_user_site_ids = 'ac100000-0000-4000-8000-000000000002';

SELECT ok(
  (SELECT count(*)::integer FROM action_rules) >= 1,
  'Operator can SELECT action_rules for own tenant'
);

-- ── Test 8: Operator CANNOT INSERT rules (admin_required policy) ─────────────
SELECT throws_ok(
  $$
  INSERT INTO action_rules
      (tenant_id, name, rule_type, threshold_value)
  VALUES
      ('ac100000-0000-4000-8000-000000000001',
       'Op Cannot Create', 'threshold', 1)
  $$,
  '42501',
  NULL,
  'Operator cannot INSERT action_rules (admin_required)'
);

-- ── Test 9: Action log scoped to tenant ──────────────────────────────────────
SET LOCAL app.current_actor_role = 'admin';

-- Insert a log entry for Tenant A and one for Tenant B (as traxia_service)
SET LOCAL ROLE traxia_service;
INSERT INTO action_log (rule_id, tenant_id, status, payload_summary)
VALUES ('ac100000-0000-4000-8000-000000000006', 'ac100000-0000-4000-8000-000000000001', 'sent', 'Test A');
INSERT INTO action_log (rule_id, tenant_id, status, payload_summary)
VALUES ('ac200000-0000-4000-8000-000000000006', 'ac200000-0000-4000-8000-000000000001', 'sent', 'Test B');

-- Now read as Tenant A admin — must see only Tenant A's log entry
SET LOCAL ROLE traxia_app;
SET LOCAL app.current_tenant_id  = 'ac100000-0000-4000-8000-000000000001';
SET LOCAL app.current_actor_role = 'admin';

SELECT is(
  (SELECT count(*)::integer FROM action_log),
  1,
  'Action log scoped to tenant — Tenant A sees only own log entries'
);

-- ── Test 10: NEGATIVE — cross-tenant engine isolation ────────────────────────
-- This is the critical test: even if a rule's zone_id points to Tenant B's zone,
-- when evaluated inside Tenant A's context (admin_conn_for_tenant(Tenant A)),
-- zone_dwell_sessions_isolation RLS blocks access to Zone B rows.
-- Seed has 10 active dwell sessions in Zone B. From Tenant A's context: 0 visible.

SELECT is(
  (
    SELECT COUNT(DISTINCT zds.person_id)::integer
    FROM zone_dwell_sessions zds
    WHERE zds.zone_id = 'ac200000-0000-4000-8000-000000000004'  -- Zone B
      AND zds.exited_at IS NULL
  ),
  0,
  'NEGATIVE: Tenant A context sees ZERO sessions from Tenant B zone '
  '(zone_dwell_sessions_isolation RLS enforced) — engine never fires on B data'
);

SELECT * FROM finish();

ROLLBACK;
