-- Tests (§ Fase 2): Backoffice RLS isolation.
--
-- Runs inside BEGIN/ROLLBACK (no persistent data).
-- All app-role operations use SET LOCAL ROLE traxia_app + session GUCs, never
-- superuser/BYPASSRLS — matching exactly what the backoffice API does.
--
-- Note on UPDATE RLS: PostgreSQL's USING clause for UPDATE acts as a row filter
-- (silently 0 rows affected, no error), while WITH CHECK raises 42501 on INSERT.
-- Tests for blocked UPDATEs use is() to verify the row is unchanged, not throws_ok.
--
-- Coverage:
--  (1)  Admin INSERT user into own tenant → success
--  (2)  Admin INSERT user_site_assignment for own site → success
--  (3)  Admin INSERT user_site_assignment for cross-tenant site → 42501
--  (4)  Operator INSERT into users → 42501
--  (5)  Admin INSERT partner into own tenant → success
--  (6)  Admin INSERT partner into another tenant → 42501
--  (7)  Admin INSERT staff_exclusion zone on own camera → success
--  (8)  Admin UPDATE partner status → success (revocation path)
--  (9)  Operator UPDATE partner → silently blocked (0 rows, status unchanged)
-- (10)  zone_dwell_summary excludes staff_exclusion zones
-- (11)  zone_dwell_summary includes non-staff zones
-- (12)  Partner Viewer SELECT on users returns only own user row
-- (13)  Admin DELETE user_site_assignment → success

BEGIN;

SELECT plan(13);

-- ── UUIDs for this test (fixed so cross-references are unambiguous) ───────────
-- Seeded by 00_backoffice_seed.sql:
-- tenant_a : bb100000-0000-4000-8000-000000000001
-- tenant_b : bb200000-0000-4000-8000-000000000001
-- site_a1  : bb100000-0000-4000-8000-000000000002
-- site_b1  : bb200000-0000-4000-8000-000000000002
-- cam_a1   : bb100000-0000-4000-8000-000000000004
-- admin_a  : bb100000-0000-4000-8000-000000000010

-- ── Context: Tenant A admin ───────────────────────────────────────────────────
SET LOCAL ROLE traxia_app;
SET LOCAL app.current_tenant_id   = 'bb100000-0000-4000-8000-000000000001';
SET LOCAL app.current_actor_role  = 'admin';
SET LOCAL app.current_user_id     = 'bb100000-0000-4000-8000-000000000010';
SET LOCAL app.provision_tenant_id = 'bb100000-0000-4000-8000-000000000001';
-- motor_site_id needed for zone_dwell_sessions ingest policy
SET LOCAL app.motor_site_id       = 'bb100000-0000-4000-8000-000000000002';

-- (1) Admin inserts a new operator user for own tenant → success
SELECT lives_ok(
  $$
  INSERT INTO users (id, tenant_id, email, role, status)
  VALUES ('bb190000-0000-0000-0000-000000000001',
          'bb100000-0000-4000-8000-000000000001',
          'op1@test.com', 'operator', 'invited')
  $$,
  'Admin can INSERT user into own tenant'
);

-- (2) Admin assigns the operator to Site A-1 → success
SELECT lives_ok(
  $$
  INSERT INTO user_site_assignments (user_id, site_id)
  VALUES ('bb190000-0000-0000-0000-000000000001',
          'bb100000-0000-4000-8000-000000000002')
  $$,
  'Admin can INSERT user_site_assignment for own site'
);

-- (3) Admin assigns a user to Site B-1 (cross-tenant) → 42501
SELECT throws_ok(
  $$
  INSERT INTO user_site_assignments (user_id, site_id)
  VALUES ('bb190000-0000-0000-0000-000000000001',
          'bb200000-0000-4000-8000-000000000002')
  $$,
  '42501',
  'new row violates row-level security policy for table "user_site_assignments"',
  'Admin cannot assign a user to a cross-tenant site'
);

-- (4) Operator cannot INSERT into users → 42501
SET LOCAL app.current_actor_role  = 'operator';
SET LOCAL app.current_user_site_ids = 'bb100000-0000-4000-8000-000000000002';
SELECT throws_ok(
  $$
  INSERT INTO users (tenant_id, email, role, status)
  VALUES ('bb100000-0000-4000-8000-000000000001', 'op2@test.com', 'viewer', 'invited')
  $$,
  '42501',
  'new row violates row-level security policy for table "users"',
  'Operator cannot INSERT into users table'
);
SET LOCAL app.current_actor_role  = 'admin';

-- (5) Admin can INSERT partner into own tenant → success
SELECT lives_ok(
  $$
  INSERT INTO partners (id, tenant_id, name, status)
  VALUES ('bb180000-0000-0000-0000-000000000001',
          'bb100000-0000-4000-8000-000000000001',
          'Test Partner', 'active')
  $$,
  'Admin can INSERT partner into own tenant'
);

-- (6) Admin cannot INSERT partner into another tenant → 42501
SELECT throws_ok(
  $$
  INSERT INTO partners (id, tenant_id, name, status)
  VALUES ('bb180000-0000-0000-0000-000000000099',
          'bb200000-0000-4000-8000-000000000001',
          'Cross-Tenant Partner', 'active')
  $$,
  '42501',
  'new row violates row-level security policy for table "partners"',
  'Admin cannot INSERT partner into another tenant'
);

-- (7) Admin inserts a staff_exclusion zone on own camera → success
SELECT lives_ok(
  $$
  INSERT INTO zones (id, camera_id, owner_type, owner_tenant_id, name, zone_type, coordinates)
  VALUES ('bb170000-0000-0000-0000-000000000001',
          'bb100000-0000-4000-8000-000000000004',
          'TENANT', 'bb100000-0000-4000-8000-000000000001',
          'Staff Entry Area', 'staff_exclusion',
          '{"type":"polygon","points":[[0,0],[50,0],[50,50],[0,50]]}'::jsonb)
  $$,
  'Admin can INSERT staff_exclusion zone on own camera'
);

-- (8) Admin can UPDATE partner status (revocation path) → success
SELECT lives_ok(
  $$
  UPDATE partners SET status = 'inactive'
  WHERE id = 'bb180000-0000-0000-0000-000000000001'
  $$,
  'Admin can UPDATE partner status (revocation path)'
);

-- (9) Operator UPDATE partner is silently blocked by RLS (USING filter, 0 rows, no error).
--     We attempt to re-activate the partner as an operator; status must remain 'inactive'.
SET LOCAL app.current_actor_role = 'operator';
UPDATE partners SET status = 'active'
WHERE id = 'bb180000-0000-0000-0000-000000000001';
SET LOCAL app.current_actor_role = 'admin';
SELECT is(
  (SELECT status FROM partners WHERE id = 'bb180000-0000-0000-0000-000000000001'),
  'inactive',
  'Operator UPDATE on partner silently blocked by RLS (USING filter) — status unchanged'
);

-- (10) & (11) zone_dwell_summary excludes staff_exclusion, includes non-staff
-- Insert a non-excluded zone on the same camera
INSERT INTO zones (id, camera_id, owner_type, owner_tenant_id, name, zone_type, coordinates)
VALUES ('bb170000-0000-0000-0000-000000000002',
        'bb100000-0000-4000-8000-000000000004',
        'TENANT', 'bb100000-0000-4000-8000-000000000001',
        'Shelf A', 'shelf',
        '{"type":"polygon","points":[[0,0],[50,0],[50,50],[0,50]]}'::jsonb);

-- Insert dwell sessions for both zones (motor_site_id is already set above)
INSERT INTO zone_dwell_sessions (zone_id, person_id, entered_at, exited_at, dwell_seconds)
VALUES
  ('bb170000-0000-0000-0000-000000000001', 'staff-1',
   now() - interval '10 minutes', now() - interval '5 minutes', 300),
  ('bb170000-0000-0000-0000-000000000002', 'customer-1',
   now() - interval '10 minutes', now() - interval '8 minutes', 120);

SELECT is(
  (SELECT count(*)::integer FROM zone_dwell_summary
   WHERE zone_type = 'staff_exclusion'
     AND zone_id   = 'bb170000-0000-0000-0000-000000000001'),
  0,
  'zone_dwell_summary excludes staff_exclusion zones from aggregates'
);

SELECT is(
  (SELECT count(*)::integer FROM zone_dwell_summary
   WHERE zone_type = 'shelf'
     AND zone_id   = 'bb170000-0000-0000-0000-000000000002'),
  1,
  'zone_dwell_summary includes non-staff zones'
);

-- (12) Partner Viewer sees only their own user row (not full tenant)
INSERT INTO partners (id, tenant_id, name, status)
VALUES ('bb160000-0000-0000-0000-000000000001',
        'bb100000-0000-4000-8000-000000000001',
        'Viewer Partner', 'active');

INSERT INTO users (id, tenant_id, partner_id, email, role, status)
VALUES ('bb150000-0000-0000-0000-000000000001',
        'bb100000-0000-4000-8000-000000000001',
        'bb160000-0000-0000-0000-000000000001',
        'pv@partner.com', 'viewer', 'active');

SET LOCAL app.current_actor_role  = 'viewer';
SET LOCAL app.current_partner_id  = 'bb160000-0000-0000-0000-000000000001';
SET LOCAL app.current_user_id     = 'bb150000-0000-0000-0000-000000000001';

SELECT is(
  (SELECT count(*)::integer FROM users),
  1,
  'Partner Viewer sees only their own user row, not full tenant'
);

-- Back to admin for the DELETE test
SET LOCAL app.current_actor_role  = 'admin';
SET LOCAL app.current_user_id     = 'bb100000-0000-4000-8000-000000000010';
SET LOCAL app.current_partner_id  = '';

-- (13) Admin can DELETE user_site_assignment
SELECT lives_ok(
  $$
  DELETE FROM user_site_assignments
  WHERE user_id = 'bb190000-0000-0000-0000-000000000001'
    AND site_id = 'bb100000-0000-4000-8000-000000000002'
  $$,
  'Admin can DELETE user_site_assignment'
);

SELECT * FROM finish();

ROLLBACK;
