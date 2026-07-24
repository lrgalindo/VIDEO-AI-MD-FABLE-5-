-- Test: operator scoped to Zona 10 (b1) cannot see Zona 4 (b2) tracking rows.
BEGIN;
SET LOCAL ROLE traxia_app;
SELECT plan(1);

SET LOCAL app.current_tenant_id      = '00000000-0000-4000-8000-0000000000a1';
SET LOCAL app.current_partner_id     = '';
SET LOCAL app.current_actor_role     = 'operator';
SET LOCAL app.current_user_site_ids  = '00000000-0000-4000-8000-0000000000b1';

SELECT is(
  (SELECT count(*)
     FROM tracking_coordinates tc
     JOIN cameras c ON c.id = tc.camera_id
    WHERE c.site_id = '00000000-0000-4000-8000-0000000000b2')::int,
  0,
  'Operator asignado solo a Zona 10 no ve ninguna fila de Zona 4, aunque ambas sean del mismo tenant'
);

SELECT * FROM finish();
ROLLBACK;
