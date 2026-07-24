/**
 * E2E — Tenant Admin role.
 *
 * Verifies the Tenant Admin sees ALL items in the SDD §4.1 matrix:
 *   Tráfico, Comparativo, Dwell Time, Zonas, Copiloto, Hallazgos,
 *   Motor de Acciones, Exportar, Usuarios, Partners
 *
 * Confirms that out-of-scope modules (Backoffice, Reventa, Fleet, Facturación)
 * are NEVER rendered in the nav (not implemented at MLP scope).
 */
import { test, expect } from '@playwright/test'
import { tokens, mockApi, loginAs } from './helpers'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('tenant admin sees traffic page after login', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await expect(page.locator('[data-testid="traffic-chart"], [data-testid="traffic-heatmap"]').first()).toBeVisible()
})

test('tenant admin nav contains all Fase 3 items including Motor de Acciones and Hallazgos', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  const nav = page.locator('nav')
  await expect(nav.getByText('Tráfico', { exact: false })).toBeVisible()
  await expect(nav.getByText('Comparativo')).toBeVisible()
  await expect(nav.getByText('Dwell Time')).toBeVisible()
  await expect(nav.getByText('Zonas', { exact: false })).toBeVisible()
  await expect(nav.getByText('Copiloto')).toBeVisible()
  await expect(nav.getByText('Hallazgos')).toBeVisible()
  await expect(nav.getByText('Motor de Acciones')).toBeVisible()
  await expect(nav.getByText('Exportar')).toBeVisible()
  await expect(nav.getByText('Usuarios')).toBeVisible()
  await expect(nav.getByText('Partners')).toBeVisible()
})

test('tenant admin can navigate to Comparison page', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.click('nav >> text=Comparativo')
  await page.waitForURL(/\/comparison/)
  await expect(page.locator('[data-testid="comparison-table"]')).toBeVisible()
})

test('tenant admin can navigate to Zones page', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.click('nav >> text=Zonas')
  await page.waitForURL(/\/zones/)
  await expect(page.locator('[data-testid="zone-canvas"]')).toBeVisible()
})

test('tenant admin can navigate to Users page', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.click('nav >> text=Usuarios')
  await page.waitForURL(/\/users/)
  await expect(page.locator('[data-testid="users-table"]')).toBeVisible()
})

test('tenant admin can navigate to Partners page', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.click('nav >> text=Partners')
  await page.waitForURL(/\/partners/)
  await expect(page.locator('[data-testid="partner-submit-btn"]')).toBeVisible()
})

test('out-of-scope modules are absent from the DOM (not just hidden)', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  // Motor de Acciones IS now visible to admins — not in this list.
  // The remaining modules don't exist at MLP scope — must be absent from DOM entirely.
  await expect(page.getByText('Reventa',    { exact: false })).toHaveCount(0)
  await expect(page.getByText('Fleet',      { exact: false })).toHaveCount(0)
  await expect(page.getByText('Facturación', { exact: false })).toHaveCount(0)
  await expect(page.getByText('Backoffice', { exact: false })).toHaveCount(0)
})

test('tenant admin can navigate to Motor de Acciones page', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.click('nav >> text=Motor de Acciones')
  await page.waitForURL(/\/actions/)
  await expect(page.locator('[data-testid="actions-tab-rules"]')).toBeVisible()
  await expect(page.locator('[data-testid="actions-tab-channels"]')).toBeVisible()
  await expect(page.locator('[data-testid="actions-tab-log"]')).toBeVisible()
})

test('tenant admin can navigate to Hallazgos page', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.click('nav >> text=Hallazgos')
  await page.waitForURL(/\/findings/)
  await expect(page.locator('[data-testid="finding-row"]').first()).toBeVisible()
})
