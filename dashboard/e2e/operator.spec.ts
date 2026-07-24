/**
 * E2E — Regional Operator role.
 *
 * SDD §4.1 matrix for Operator:
 *   ✓ Tráfico/Heatmap, Dwell Time, Copiloto, Exportar
 *   ✗ Comparativo (admin only), Zonas (admin only), Usuarios (admin only), Partners (admin only)
 *
 * Also verifies unauthenticated access redirects to /login.
 */
import { test, expect } from '@playwright/test'
import { tokens, mockApi, loginAs } from './helpers'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('unauthenticated visit to / redirects to /login', async ({ page }) => {
  await page.goto('/')
  await page.waitForURL(/\/login/)
  await expect(page.locator('[data-testid="login-form"]')).toBeVisible()
})

test('operator sees traffic, dwell, copilot, export in nav', async ({ page }) => {
  await loginAs(page, tokens.operator())
  const nav = page.locator('nav')
  await expect(nav.getByText('Tráfico', { exact: false })).toBeVisible()
  await expect(nav.getByText('Dwell Time')).toBeVisible()
  await expect(nav.getByText('Copiloto')).toBeVisible()
  await expect(nav.getByText('Exportar')).toBeVisible()
})

test('operator: admin-only nav links are absent from the DOM', async ({ page }) => {
  await loginAs(page, tokens.operator())
  // Nav filters these out entirely — toHaveCount(0) verifies DOM absence, not just hiding.
  await expect(page.locator('[data-testid="nav-comparison"]')).toHaveCount(0)
  await expect(page.locator('[data-testid="nav-zones"]')).toHaveCount(0)
  await expect(page.locator('[data-testid="nav-users"]')).toHaveCount(0)
  await expect(page.locator('[data-testid="nav-partners"]')).toHaveCount(0)
})

test('operator navigating directly to /comparison gets redirected', async ({ page }) => {
  await loginAs(page, tokens.operator())
  await page.goto('/comparison')
  // RequireAuth passes (logged in), AdminOnly redirects to /
  await page.waitForURL(/\/(traffic|dwell|$)/)
  await expect(page.locator('[data-testid="comparison-table"]')).not.toBeVisible()
})

test('operator navigating directly to /zones gets redirected', async ({ page }) => {
  await loginAs(page, tokens.operator())
  await page.goto('/zones')
  await page.waitForURL(/\/(traffic|dwell|$)/)
  await expect(page.locator('[data-testid="zone-canvas"]')).not.toBeVisible()
})

test('operator sees dwell time table', async ({ page }) => {
  await loginAs(page, tokens.operator())
  await page.click('nav >> text=Dwell Time')
  await page.waitForURL(/\/dwell/)
  await expect(page.locator('[data-testid="dwell-table"]')).toBeVisible()
})

test('operator sees copilot interface', async ({ page }) => {
  await loginAs(page, tokens.operator())
  await page.click('nav >> text=Copiloto')
  await page.waitForURL(/\/copilot/)
  await expect(page.locator('[data-testid="copilot-input"]')).toBeVisible()
})
