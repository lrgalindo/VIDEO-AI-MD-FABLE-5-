-- E2E smoke-test seed data.
-- Runs as postgres (superuser) so RLS is bypassed for these seed inserts.
-- All UUIDs are fixed so smoke_test.py can reference them by constant.

BEGIN;

INSERT INTO resellers (id, name, status)
VALUES ('a1e2e000-0000-0000-0000-000000000001', 'E2E Reseller', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO tenants (id, reseller_id, name, vertical_type, status)
VALUES (
    'b2e2e000-0000-0000-0000-000000000001',
    'a1e2e000-0000-0000-0000-000000000001',
    'E2E Tenant',
    'retail',
    'active'
) ON CONFLICT (id) DO NOTHING;

INSERT INTO sites (id, tenant_id, name, status)
VALUES (
    'c3e2e000-0000-0000-0000-000000000001',
    'b2e2e000-0000-0000-0000-000000000001',
    'E2E Site',
    'active'
) ON CONFLICT (id) DO NOTHING;

-- rtsp_url_ciphertext: Fernet-encrypted with TEST_RTSP_ENCRYPTION_KEY (see tests/conftest.py).
INSERT INTO cameras (id, site_id, name, rtsp_url_ciphertext, rtsp_url_key_id, status)
VALUES (
    'd4e2e000-0000-0000-0000-000000000001',
    'c3e2e000-0000-0000-0000-000000000001',
    'E2E Camera',
    decode('67414141414142715942516856706f76416942786e687a6335795f424466574f786b7a714f775a54395447766f4c4a575649764a4f7a68536f47633149505a524a5f765a6f54574f6d766f55306e4d746271426f61724d2d2d5738332d777049554c7135784239776f44524873426f32337a78705a67773d', 'hex'),
    'test-key-v1',
    'active'
) ON CONFLICT (id) DO NOTHING;

-- Edge gateway: activation_code = 'e2e-smoke-code-2026'
INSERT INTO edge_gateways (
    id, site_id, vertical_type, status,
    activation_code_hash, activation_code_expires_at
)
VALUES (
    'e2e-gateway-001',
    'c3e2e000-0000-0000-0000-000000000001',
    'retail',
    'offline',
    encode(sha256('e2e-smoke-code-2026'::bytea), 'hex'),
    now() + interval '2 hours'
) ON CONFLICT (id) DO NOTHING;

-- Zone linked to the E2E camera (TENANT-owned so both admin and partner can be tested)
INSERT INTO zones (id, camera_id, owner_type, owner_tenant_id, name, zone_type, coordinates)
VALUES (
    'f5e2e000-0000-0000-0000-000000000001',
    'd4e2e000-0000-0000-0000-000000000001',
    'TENANT',
    'b2e2e000-0000-0000-0000-000000000001',
    'E2E Zona Checkout',
    'checkout',
    '[[0,0],[320,0],[320,240],[0,240]]'
) ON CONFLICT (id) DO NOTHING;

-- ── Users ─────────────────────────────────────────────────────────────────────
-- Tenant admin user (JWT: sub=u-e2e-admin, tid=b2e2e..., role=admin)
INSERT INTO users (id, tenant_id, email, role, status)
VALUES (
    'aaee2e00-0000-0000-0000-000000000001',
    'b2e2e000-0000-0000-0000-000000000001',
    'e2e-admin@traxia.test',
    'admin',
    'active'
) ON CONFLICT (id) DO NOTHING;

-- ── Motor de Acciones: action rule + channel + binding ────────────────────────
-- Threshold rule: ≥1 person in zone for ≥1 minute → fires immediately given seed dwell data
INSERT INTO action_rules (
    id, tenant_id, site_id, zone_id, name, rule_type,
    threshold_value, threshold_window_minutes, enabled, created_by
)
VALUES (
    'bb1e2e00-0000-0000-0000-000000000001',
    'b2e2e000-0000-0000-0000-000000000001',
    'c3e2e000-0000-0000-0000-000000000001',
    'f5e2e000-0000-0000-0000-000000000001',
    'E2E Threshold Rule',
    'threshold',
    1,      -- threshold_value: 1 person
    1,      -- threshold_window_minutes: 1 minute (fires quickly for smoke test)
    TRUE,
    'aaee2e00-0000-0000-0000-000000000001'
) ON CONFLICT (id) DO NOTHING;

-- Slack channel pointing at httpbin (accepts any POST, returns 200)
INSERT INTO action_channels (
    id, tenant_id, name, channel_type, config_json, enabled
)
VALUES (
    'cc2e2e00-0000-0000-0000-000000000001',
    'b2e2e000-0000-0000-0000-000000000001',
    'E2E Webhook via httpbin',
    'slack',
    '{"webhook_url": "http://httpbin:80/post"}'::jsonb,
    TRUE
) ON CONFLICT (id) DO NOTHING;

-- Bind rule to channel
INSERT INTO action_rule_channels (rule_id, channel_id)
VALUES (
    'bb1e2e00-0000-0000-0000-000000000001',
    'cc2e2e00-0000-0000-0000-000000000001'
) ON CONFLICT DO NOTHING;

-- ── zone_dwell_sessions: stuck person triggers threshold rule ─────────────────
-- Active session (exited_at IS NULL) started 10 minutes ago → threshold=1 fires immediately
INSERT INTO zone_dwell_sessions (id, zone_id, person_id, entered_at, exited_at, dwell_seconds)
VALUES (
    'dd3e2e00-0000-0000-0000-000000000001',
    'f5e2e000-0000-0000-0000-000000000001',
    'track-e2e-001',
    now() - interval '10 minutes',
    NULL,
    NULL
) ON CONFLICT (id) DO NOTHING;

-- ── zone_dwell_sessions: baseline data for dwell-drop audit trigger ──────────
-- 6 completed sessions from 3-7 days ago with high dwell (baseline)
-- + 2 recent sessions with low dwell → drop below 50% threshold
INSERT INTO zone_dwell_sessions (id, zone_id, person_id, entered_at, exited_at, dwell_seconds)
VALUES
    ('ee4e2e00-0000-0000-0000-000000000001', 'f5e2e000-0000-0000-0000-000000000001', 'track-b001', now() - interval '3 days', now() - interval '3 days' + interval '120 seconds', 120),
    ('ee4e2e00-0000-0000-0000-000000000002', 'f5e2e000-0000-0000-0000-000000000001', 'track-b002', now() - interval '3 days 1 hour', now() - interval '3 days 1 hour' + interval '130 seconds', 130),
    ('ee4e2e00-0000-0000-0000-000000000003', 'f5e2e000-0000-0000-0000-000000000001', 'track-b003', now() - interval '4 days', now() - interval '4 days' + interval '115 seconds', 115),
    ('ee4e2e00-0000-0000-0000-000000000004', 'f5e2e000-0000-0000-0000-000000000001', 'track-b004', now() - interval '5 days', now() - interval '5 days' + interval '125 seconds', 125),
    ('ee4e2e00-0000-0000-0000-000000000005', 'f5e2e000-0000-0000-0000-000000000001', 'track-b005', now() - interval '6 days', now() - interval '6 days' + interval '110 seconds', 110),
    ('ee4e2e00-0000-0000-0000-000000000006', 'f5e2e000-0000-0000-0000-000000000001', 'track-b006', now() - interval '7 days' + interval '1 hour', now() - interval '7 days' + interval '1 hour' + interval '120 seconds', 120)
ON CONFLICT (id) DO NOTHING;

-- 2 recent sessions (last 2h) with very low dwell → triggers dwell drop audit
INSERT INTO zone_dwell_sessions (id, zone_id, person_id, entered_at, exited_at, dwell_seconds)
VALUES
    ('ee4e2e00-0000-0000-0000-000000000007', 'f5e2e000-0000-0000-0000-000000000001', 'track-r001', now() - interval '30 minutes', now() - interval '30 minutes' + interval '5 seconds', 5),
    ('ee4e2e00-0000-0000-0000-000000000008', 'f5e2e000-0000-0000-0000-000000000001', 'track-r002', now() - interval '15 minutes', now() - interval '15 minutes' + interval '6 seconds', 6)
ON CONFLICT (id) DO NOTHING;

COMMIT;
