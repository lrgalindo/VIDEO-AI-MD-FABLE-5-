/**
 * E2E — Partner Viewer role (role='viewer', pid set).
 *
 * SDD §4.1 matrix for Partner (any role with pid):
 *   ✓ Tráfico/Heatmap (scoped), Dwell Time (own zones — RLS), Copiloto, Hallazgos, Exportar
 *   ✗ Comparativo, Zonas, Usuarios, Partners, Motor de Acciones — NEVER rendered
 *   ✗ Backoffice, Reventa, Fleet, Facturación — NEVER rendered
 *
 * Data scoping (partners see only their zones) is guaranteed by RLS on the server.
 * These E2E tests focus on the UI visibility guarantee and absence from DOM.
 */
import { test, expect } from '@playwright/test'
import { tokens, mockApi, loginAs } from './helpers'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('partner viewer logs in and reaches traffic page', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  // Traffic is visible to partners (their scoped traffic view)
  await expect(page.locator('[data-testid="traffic-chart"], [data-testid="traffic-heatmap"]').first()).toBeVisible()
})

test('partner viewer nav shows traffic, dwell, copilot, hallazgos, export — no admin items', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  const nav = page.locator('nav')

  // Visible to partners (Fase 3 adds Hallazgos)
  await expect(nav.getByText('Tráfico', { exact: false })).toBeVisible()
  await expect(nav.getByText('Dwell Time')).toBeVisible()
  await expect(nav.getByText('Copiloto')).toBeVisible()
  await expect(nav.getByText('Hallazgos')).toBeVisible()
  await expect(nav.getByText('Exportar')).toBeVisible()

  // Admin nav links must be absent from the DOM (not just hidden)
  await expect(page.locator('[data-testid="nav-comparison"]')).toHaveCount(0)
  await expect(page.locator('[data-testid="nav-zones"]')).toHaveCount(0)
  await expect(page.locator('[data-testid="nav-users"]')).toHaveCount(0)
  await expect(page.locator('[data-testid="nav-partners"]')).toHaveCount(0)
  // Motor de Acciones — critical: must never appear in partner DOM
  await expect(page.locator('[data-testid="nav-actions"]')).toHaveCount(0)
})

test('partner viewer cannot reach /comparison via direct URL', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await page.goto('/comparison')
  await page.waitForURL(/\/(traffic|dwell|$)/)
  await expect(page.locator('[data-testid="comparison-table"]')).not.toBeVisible()
})

test('partner viewer cannot reach /zones via direct URL', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await page.goto('/zones')
  await page.waitForURL(/\/(traffic|dwell|$)/)
  await expect(page.locator('[data-testid="zone-canvas"]')).not.toBeVisible()
})

test('partner viewer cannot reach /users via direct URL', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await page.goto('/users')
  await page.waitForURL(/\/(traffic|dwell|$)/)
  await expect(page.locator('[data-testid="users-table"]')).not.toBeVisible()
})

test('partner viewer cannot reach /partners via direct URL', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await page.goto('/partners')
  await page.waitForURL(/\/(traffic|dwell|$)/)
  await expect(page.locator('[data-testid="partner-submit-btn"]')).not.toBeVisible()
})

test('partner viewer sees dwell time (scoped to their zones via RLS)', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await page.click('nav >> text=Dwell Time')
  await page.waitForURL(/\/dwell/)
  await expect(page.locator('[data-testid="dwell-table"]')).toBeVisible()
})

test('partner viewer can use copilot', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await page.click('nav >> text=Copiloto')
  await page.waitForURL(/\/copilot/)
  await expect(page.locator('[data-testid="copilot-input"]')).toBeVisible()
})

test('partner viewer can access export', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await page.click('nav >> text=Exportar')
  await page.waitForURL(/\/export/)
  await expect(page.locator('[data-testid="export-csv-btn"]')).toBeVisible()
})

test('forbidden modules are absent from the DOM for partner', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  // toHaveCount(0) proves ABSENCE from the DOM — not just hidden with CSS.
  // These modules are not in NAV_ITEMS for partner and have no accessible route.
  await expect(page.getByText('Reventa',          { exact: false })).toHaveCount(0)
  await expect(page.getByText('Fleet',             { exact: false })).toHaveCount(0)
  await expect(page.getByText('Facturación',       { exact: false })).toHaveCount(0)
  await expect(page.getByText('Motor de Acciones', { exact: false })).toHaveCount(0)
  await expect(page.getByText('Backoffice',        { exact: false })).toHaveCount(0)
})

test('partner viewer can navigate to Hallazgos page and see findings', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await page.click('nav >> text=Hallazgos')
  await page.waitForURL(/\/findings/)
  await expect(page.locator('[data-testid="finding-row"]').first()).toBeVisible()
})

test('partner viewer cannot reach /actions via direct URL', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await page.goto('/actions')
  // The React AdminOnly component redirects to / as a UX convenience — this is NOT the
  // security mechanism. The real protection is require_tenant_admin on every Motor de
  // Acciones endpoint server-side (returns 403 for any non-admin or partner-scoped token,
  // regardless of what the frontend does). Same principle as all other admin-only routes.
  await page.waitForURL(/\/(traffic|dwell|$)/)
  await expect(page.locator('[data-testid="actions-tab-rules"]')).not.toBeVisible()
})
