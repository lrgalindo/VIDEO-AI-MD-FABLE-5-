/**
 * E2E — Fase 3 interface tests.
 *
 * Covers:
 *   (a) Motor de Acciones — admin only, CRUD rules + channels, WhatsApp cost gate
 *   (b) Copiloto — real API call via mocked backend; partner scoping is server-side
 *   (c) Hallazgos — visible to admin and partner; Motor de Acciones never in partner DOM
 *
 * All /v1/* calls are mocked (see helpers.ts). Data scoping per-zone is guaranteed
 * by RLS server-side; these tests verify UI-level role isolation only.
 */
import { test, expect } from '@playwright/test'
import { tokens, mockApi, loginAs } from './helpers'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

// ── (a) Motor de Acciones — Tenant Admin ─────────────────────────────────────

test('Motor de Acciones: admin sees three tabs on load', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.goto('/actions')
  await expect(page.locator('[data-testid="actions-tab-rules"]')).toBeVisible()
  await expect(page.locator('[data-testid="actions-tab-channels"]')).toBeVisible()
  await expect(page.locator('[data-testid="actions-tab-log"]')).toBeVisible()
})

test('Motor de Acciones: rule form rendered on Reglas tab', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.goto('/actions')
  await expect(page.locator('[data-testid="rule-type-select"]')).toBeVisible()
  await expect(page.locator('[data-testid="rule-name-input"]')).toBeVisible()
  await expect(page.locator('[data-testid="rule-submit-btn"]')).toBeVisible()
})

test('Motor de Acciones: threshold fields appear only for threshold type', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.goto('/actions')
  // Default type is threshold — extra fields visible
  await expect(page.locator('[data-testid="rule-threshold-input"]')).toBeVisible()
  await expect(page.locator('[data-testid="rule-window-input"]')).toBeVisible()
  // Switch to SOP type — extra fields disappear
  await page.selectOption('[data-testid="rule-type-select"]', 'sop_staff_absent_checkout')
  await expect(page.locator('[data-testid="rule-threshold-input"]')).not.toBeVisible()
  await expect(page.locator('[data-testid="rule-window-input"]')).not.toBeVisible()
})

test('Motor de Acciones: WhatsApp cost section hidden for non-WhatsApp channels', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.goto('/actions')
  await page.click('[data-testid="actions-tab-channels"]')
  // Default channel type is slack — no WhatsApp cost section
  await expect(page.locator('[data-testid="whatsapp-cost-section"]')).not.toBeVisible()
})

test('Motor de Acciones: WhatsApp cost section appears when whatsapp selected', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.goto('/actions')
  await page.click('[data-testid="actions-tab-channels"]')
  await page.selectOption('[data-testid="channel-type-select"]', 'whatsapp')
  await expect(page.locator('[data-testid="whatsapp-cost-section"]')).toBeVisible()
  await expect(page.locator('[data-testid="whatsapp-cost-input"]')).toBeVisible()
})

test('Motor de Acciones: WhatsApp submit disabled until cost declared', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.goto('/actions')
  await page.click('[data-testid="actions-tab-channels"]')
  await page.selectOption('[data-testid="channel-type-select"]', 'whatsapp')
  await page.fill('[data-testid="channel-name-input"]', 'WA Canal')
  await page.fill('[data-testid="channel-config-input"]', '{"phone_number_id":"123","access_token":"abc"}')
  // Button is disabled before cost is entered
  await expect(page.locator('[data-testid="channel-submit-btn"]')).toBeDisabled()
  // Enter cost → button becomes enabled
  await page.fill('[data-testid="whatsapp-cost-input"]', '0.0630')
  await expect(page.locator('[data-testid="channel-submit-btn"]')).not.toBeDisabled()
})

test('Motor de Acciones: NEVER in Partner DOM (toHaveCount(0))', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  // Confirm the nav link is absent — not just hidden
  await expect(page.locator('[data-testid="nav-actions"]')).toHaveCount(0)
  await expect(page.getByText('Motor de Acciones', { exact: false })).toHaveCount(0)
})

// ── (b) Copiloto — real API call ──────────────────────────────────────────────

test('Copiloto: admin sends question and receives mocked answer', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.goto('/copilot')
  await page.fill('[data-testid="copilot-input"]', '¿Cuál fue el día más concurrido?')
  await page.click('[data-testid="copilot-submit"]')
  await expect(page.locator('[data-testid="copilot-answer"]')).toBeVisible()
  await expect(page.locator('[data-testid="copilot-answer"]')).toContainText('Respuesta de prueba')
})

test('Copiloto: partner sends question and receives answer (scope enforced server-side)', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await page.goto('/copilot')
  await page.fill('[data-testid="copilot-input"]', '¿Qué zonas tienen mayor dwell?')
  await page.click('[data-testid="copilot-submit"]')
  await expect(page.locator('[data-testid="copilot-answer"]')).toBeVisible()
})

test('Copiloto: submit button disabled when input is empty', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.goto('/copilot')
  await expect(page.locator('[data-testid="copilot-submit"]')).toBeDisabled()
  await page.fill('[data-testid="copilot-input"]', 'pregunta')
  await expect(page.locator('[data-testid="copilot-submit"]')).not.toBeDisabled()
})

// ── (c) Hallazgos ─────────────────────────────────────────────────────────────

test('Hallazgos: admin sees finding rows from mocked API', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await page.goto('/findings')
  await expect(page.locator('[data-testid="finding-row"]').first()).toBeVisible()
  await expect(page.locator('[data-testid="finding-row"]').first()).toContainText('quiebre de stock')
})

test('Hallazgos: partner sees finding rows (RLS scopes to their zones server-side)', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await page.goto('/findings')
  // The mock returns the same row for both roles — server-side RLS filters in production
  await expect(page.locator('[data-testid="finding-row"]').first()).toBeVisible()
})

test('Hallazgos: nav link present for partner (Hallazgos is in scope)', async ({ page }) => {
  await loginAs(page, tokens.partnerViewer())
  await expect(page.locator('[data-testid="nav-findings"]')).toBeVisible()
})

test('Hallazgos: nav link present for admin', async ({ page }) => {
  await loginAs(page, tokens.tenantAdmin())
  await expect(page.locator('[data-testid="nav-findings"]')).toBeVisible()
})

test('Hallazgos: snapshot <img> renders when snapshot_url present in response', async ({ page }) => {
  // The mock provides snapshot_url — verify the <img> is rendered.
  // In production, snapshot_url is a short-lived presigned R2 URL generated
  // server-side under the same RLS scope as the findings query.
  await loginAs(page, tokens.tenantAdmin())
  await page.goto('/findings')
  await expect(page.locator('[data-testid="finding-snapshot"]').first()).toBeVisible()
})

test('Hallazgos: snapshot_r2_key never appears in any rendered text', async ({ page }) => {
  // Verify the internal R2 key field is never surfaced in the UI.
  // The server strips snapshot_r2_key and replaces it with snapshot_url.
  await loginAs(page, tokens.tenantAdmin())
  await page.goto('/findings')
  const pageText = await page.locator('body').innerText()
  expect(pageText).not.toContain('snapshot_r2_key')
})
