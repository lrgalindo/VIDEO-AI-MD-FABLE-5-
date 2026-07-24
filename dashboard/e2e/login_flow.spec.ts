/**
 * Real login flow test — exercises the actual Login.tsx form and state
 * machine (credentials step -> mfa step -> redirect), unlike loginAs()
 * in helpers.ts which bypasses the UI entirely by short-circuiting
 * /v1/auth/login with a direct token.
 *
 * This test mocks only the network boundary (Supabase is external and
 * cannot be reached non-interactively in CI), but every DOM interaction —
 * typing, clicking, the mfa_required transition, the TOTP submission —
 * goes through the real component. If Login.tsx's form wiring, state
 * transitions, or fetch payloads break, this test fails; a broken
 * loginAs() mock alone would not catch that.
 */
import { test, expect } from '@playwright/test'
import type { Route } from '@playwright/test'

// Must include exp (far future) — Layout.tsx's isAuthenticated check requires
// token.exp > now; a payload without it silently bounces back to /login,
// which is exactly the kind of failure this test exists to catch.
const TEST_JWT =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.' +
  'eyJzdWIiOiJ1MSIsInRpZCI6InQxIiwicm9sZSI6ImFkbWluIiwiaWF0IjoxNzAwMDAwMDAwLCJleHAiOjk5OTk5OTk5OTl9.' +
  'fakesig'

test('real login form: credentials -> mfa_required -> TOTP -> redirect', async ({ page }) => {
  // Playwright matches routes LIFO — the most recently registered handler
  // is tried first. The broad /v1/** catch-all must be registered BEFORE
  // the specific auth overrides below, or it would swallow the login/mfa
  // requests before they ever reach the specific handlers.
  await page.route('/v1/**', async (route: Route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/v1/auth/login' || path === '/v1/auth/mfa/verify') return route.continue()
    return route.fulfill({ status: 200, json: [] })
  })

  // Step 1: POST /v1/auth/login returns 401 mfa_required, mirroring
  // cloud/auth/mfa.py's exact response shape (code, amr_challenge, factors).
  await page.route('**/v1/auth/login', async (route: Route) => {
    if (route.request().method() !== 'POST') return route.continue()
    const body = route.request().postDataJSON()
    expect(body.email).toBe('realuser@example.com')
    expect(body.password).toBe('correct-horse-battery-staple')
    return route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: {
          code: 'mfa_required',
          amr_challenge: { id: 'challenge-abc' },
          factors: [{ id: 'factor-xyz' }],
        },
      }),
    })
  })

  // Step 2: POST /v1/auth/mfa/verify returns the session, mirroring
  // Supabase's factor-verify response relayed by cloud/auth/mfa.py.
  await page.route('**/v1/auth/mfa/verify', async (route: Route) => {
    if (route.request().method() !== 'POST') return route.continue()
    const body = route.request().postDataJSON()
    expect(body.factor_id).toBe('factor-xyz')
    expect(body.challenge_id).toBe('challenge-abc')
    expect(body.code).toBe('123456')
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: TEST_JWT, token_type: 'bearer' }),
    })
  })

  await page.goto('/login')

  // ── Step 1: real credentials form ──────────────────────────────────────
  await expect(page.locator('[data-testid="login-form"]')).toBeVisible()
  await page.fill('[data-testid="email-input"]', 'realuser@example.com')
  await page.fill('[data-testid="password-input"]', 'correct-horse-battery-staple')
  await page.click('[data-testid="login-submit"]')

  // ── Step 2: real MFA form appears (component read mfa_required and switched) ──
  await expect(page.locator('[data-testid="mfa-form"]')).toBeVisible()
  await expect(page.locator('[data-testid="login-form"]')).toHaveCount(0)
  await page.fill('[data-testid="totp-input"]', '123456')
  await page.click('[data-testid="mfa-submit"]')

  // ── Step 3: real redirect after the component stored the token ──────────
  await page.waitForURL(/\/(traffic|dwell|copilot)/)
  const stored = await page.evaluate(() => localStorage.getItem('traxia_token'))
  expect(stored).toBe(TEST_JWT)
})

test('real login form: wrong credentials show inline error, no redirect', async ({ page }) => {
  await page.route('**/v1/auth/login', async (route: Route) => {
    if (route.request().method() !== 'POST') return route.continue()
    return route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'invalid_credentials' }),
    })
  })

  await page.goto('/login')
  await page.fill('[data-testid="email-input"]', 'wrong@example.com')
  await page.fill('[data-testid="password-input"]', 'wrong-password')
  await page.click('[data-testid="login-submit"]')

  await expect(page.locator('[data-testid="login-error"]')).toBeVisible()
  await expect(page.locator('[data-testid="mfa-form"]')).toHaveCount(0)
  expect(page.url()).toContain('/login')
})
