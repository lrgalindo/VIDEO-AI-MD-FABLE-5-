-- Test: Asset Owner retains visibility of zones ceded to a Partner (Flujo 3, v3.2 fix).
BEGIN;
SET LOCAL ROLE traxia_app;
SELECT plan(1);

SET LOCAL app.current_tenant_id  = '00000000-0000-4000-8000-0000000000a1';
SET LOCAL app.current_partner_id = '';
SET LOCAL app.current_actor_role = 'admin';

SELECT ok(
  (SELECT count(*)
     FROM zone_dwell_sessions zds
     JOIN zones z ON z.id = zds.zone_id
    WHERE z.owner_type = 'PARTNER'
      AND z.owner_partner_id = '00000000-0000-4000-8000-0000000000d1') > 0,
  'El Asset Owner conserva visibilidad de las zonas cedidas a sus Partners (Flujo 3)'
);

SELECT * FROM finish();
ROLLBACK;
