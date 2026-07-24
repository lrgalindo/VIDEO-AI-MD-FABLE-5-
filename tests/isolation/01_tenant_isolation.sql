-- Test: tenant admin only sees own tracking rows; never sees another tenant's rows.
BEGIN;
SET LOCAL ROLE traxia_app;
SELECT plan(2);

SET LOCAL app.current_tenant_id  = '00000000-0000-4000-8000-0000000000a1';
SET LOCAL app.current_partner_id = '';
SET LOCAL app.current_actor_role = 'admin';

-- All visible rows belong to tenant a1's cameras
SELECT ok(
  (SELECT count(*) FROM tracking_coordinates) =
  (SELECT count(*)
     FROM tracking_coordinates tc
     JOIN cameras c ON c.id = tc.camera_id
     JOIN sites   s ON s.id = c.site_id
    WHERE s.tenant_id = '00000000-0000-4000-8000-0000000000a1'),
  'Tenant a1 (admin) solo ve filas de sus propias cámaras'
);

-- Rows whose camera belongs to tenant a2 are invisible
SELECT is(
  (SELECT count(*)
     FROM tracking_coordinates tc
     JOIN cameras c ON c.id = tc.camera_id
     JOIN sites   s ON s.id = c.site_id
    WHERE s.tenant_id = '00000000-0000-4000-8000-0000000000a2')::int,
  0,
  'Tenant a1 nunca ve filas del tenant a2, aunque existan en la tabla física'
);

SELECT * FROM finish();
ROLLBACK;
