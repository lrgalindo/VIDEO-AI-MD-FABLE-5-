-- Test: partner d1 cannot see TENANT zones' dwell sessions,
-- and cannot see dwell sessions belonging to partner d2 (same tenant, different partner).
-- Both assertions require real data in the table — the seed inserts rows for both
-- the tenant zone (ee01) and for d2's zone (ee03).
BEGIN;
SET LOCAL ROLE traxia_app;
SELECT plan(2);

SET LOCAL app.current_tenant_id  = '';
SET LOCAL app.current_partner_id = '00000000-0000-4000-8000-0000000000d1';
SET LOCAL app.current_actor_role = 'viewer';

-- Negative: d1 cannot see dwell sessions for TENANT-owned zones.
-- Seed has ee01 in zone e101 (owner_type=TENANT). Expect 0.
SELECT is(
  (SELECT count(*)
     FROM zone_dwell_sessions zds
     JOIN zones z ON z.id = zds.zone_id
    WHERE z.owner_type = 'TENANT')::int,
  0,
  'Partner d1 nunca ve sesiones de dwell de zonas propiedad del tenant'
);

-- Negative: d1 cannot see dwell sessions for d2's zone.
-- Seed has ee03 in zone e103 (owner_partner_id=d2). The row exists physically.
-- RLS must return 0, not because there is no data, but because it is filtered.
SELECT is(
  (SELECT count(*)
     FROM zone_dwell_sessions zds
     JOIN zones z ON z.id = zds.zone_id
    WHERE z.owner_type    = 'PARTNER'
      AND z.owner_partner_id = '00000000-0000-4000-8000-0000000000d2')::int,
  0,
  'Partner d1 nunca ve las sesiones de dwell de Partner d2 (mismo tenant, distinto partner)'
);

SELECT * FROM finish();
ROLLBACK;
