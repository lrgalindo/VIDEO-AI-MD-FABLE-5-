/**
 * E2E test helpers for Traxia dashboard.
 *
 * Token generation: the dashboard reads JWTs from localStorage. We fabricate
 * tokens with the correct claim shapes using base64url encoding — no actual
 * signing is needed because the frontend only decodes the payload to determine
 * which nav items to show (authorization is enforced server-side via RLS).
 *
 * API mocking: all /v1/* routes are intercepted so tests run without a
 * running backend, focusing purely on frontend role-visibility guarantees.
 */
import type { Page, Route } from '@playwright/test'

// ── Token helpers ─────────────────────────────────────────────────────────────

function b64url(obj: unknown): string {
  return Buffer.from(JSON.stringify(obj)).toString('base64url')
}

function makeJwt(payload: Record<string, unknown>): string {
  const header = b64url({ alg: 'HS256', typ: 'JWT' })
  const body   = b64url({ ...payload, iat: 1_700_000_000, exp: 9_999_999_999 })
  return `${header}.${body}.fakesig`
}

export const tokens = {
  tenantAdmin: () => makeJwt({ sub: 'u1', tid: 't1', role: 'admin' }),
  operator:    () => makeJwt({ sub: 'u2', tid: 't1', role: 'operator', sids: ['s1'] }),
  partnerViewer: () => makeJwt({ sub: 'u3', tid: 't1', role: 'viewer', pid: 'p1', sids: ['s1'] }),
}

// ── API mock ──────────────────────────────────────────────────────────────────

export async function mockApi(page: Page) {
  await page.route('/v1/**', async (route: Route) => {
    const url  = route.request().url()
    const path = new URL(url).pathname

    if (path === '/v1/analytics/traffic')    return route.fulfill({ json: [] })
    if (path === '/v1/analytics/comparison') return route.fulfill({ json: [] })
    if (path === '/v1/analytics/dwell')      return route.fulfill({ json: [] })
    if (path === '/v1/sites')                return route.fulfill({ json: [] })
    if (path === '/v1/cameras')              return route.fulfill({ json: [] })
    if (path === '/v1/zones')                return route.fulfill({ json: [] })
    if (path === '/v1/backoffice/users' && route.request().method() === 'GET')
      return route.fulfill({ json: [] })

    // Motor de Acciones
    if (path === '/v1/actions/rules')    return route.fulfill({ json: [] })
    if (path === '/v1/actions/channels') return route.fulfill({ json: [] })
    if (path === '/v1/actions/log')      return route.fulfill({ json: [] })

    // Copiloto
    if (path === '/v1/copilot/chat' && route.request().method() === 'POST')
      return route.fulfill({
        json: {
          answer: 'Respuesta de prueba del copiloto.',
          authorized_zone_count: 2,
          model: 'claude-haiku-4-5',
        },
      })

    // Agent Findings — snapshot_url is a presigned URL from the server.
    // In prod it's short-lived (5 min). Here we use a placeholder so the <img> renders.
    if (path === '/v1/findings')
      return route.fulfill({
        json: [{
          id: 'f1',
          task_type: 'stock_audit',
          zone_id: 'z1',
          summary: 'Posible quiebre de stock detectado',
          detail: {
            recent_avg_dwell: 45,
            baseline_avg_dwell: 142,
            vision_finding: 'Shelf appears partially empty.',
            snapshot_available: true,
          },
          // snapshot_url simulates a presigned R2 URL; <img> is rendered when present
          snapshot_url: 'https://example.r2.dev/snapshots/z1/run1.jpg',
          created_at: '2026-07-20T10:00:00Z',
        }],
      })

    // Auth endpoints — handled by loginAs() interceptor, not here
    if (path === '/v1/auth/login' || path === '/v1/auth/mfa/verify')
      return route.continue()

    // Default: return empty for unknown routes
    return route.fulfill({ status: 200, json: {} })
  })
}

// ── Login helper ──────────────────────────────────────────────────────────────
//
// Mocks /v1/auth/login to return the provided JWT directly.
// This mirrors tests/lifecycle/test_mfa.py's approach of mocking the Supabase
// HTTP response — both intercept at the transport layer without a real Supabase project.

export async function loginAs(page: Page, tokenStr: string) {
  // Intercept POST /v1/auth/login and return the test JWT immediately.
  // This is the Playwright equivalent of patch("cloud.auth.mfa.httpx.Client").
  await page.route('/v1/auth/login', async (route: Route) => {
    if (route.request().method() === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: tokenStr, token_type: 'bearer' }),
      })
    }
    return route.continue()
  })

  await page.goto('/login')
  await page.fill('[data-testid="email-input"]', 'test@example.com')
  await page.fill('[data-testid="password-input"]', 'test-password')
  await page.click('[data-testid="login-submit"]')
  // Wait for redirect to dashboard
  await page.waitForURL(/\/(traffic|dwell|copilot)/)
}
