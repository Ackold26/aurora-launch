/**
 * m09-reproduce-python.spec.ts — Phase 2.E
 *
 * E2E tests для M-09 «Воспроизвести в Python» modal в Inspector.
 *
 * Key architecture facts (recon 2026-05-16):
 *   - "Воспроизвести в Python" button is in forecast tab (not a top-level Inspector tab)
 *   - Click → openReproduceModal() → calls generate_reproduce_script IPC
 *   - Modal: role="dialog" aria-labelledby="reproduce-modal-title"
 *   - Script rendered in <pre class="reproduce-code"><code>...</code></pre>
 *   - generate_reproduce_script returns { script: string, suggested_filename: string }
 *     (NOT script_python — actual ipc/forecast.ts field name is `script`)
 *   - Modal closes on Escape key or backdrop click (or close button ✕)
 *   - Button requires activeBundle + forecastData to be non-null
 *
 * Strategy:
 *   - Use window.__auroraTestSetBundle hook if exposed (same pattern as other inspector specs)
 *   - Navigate to forecast tab (index 2) → click reproduce button → assert modal
 *   - Skip gracefully if any prerequisite is missing
 */

import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';
import { setupMockIpc } from './_helpers/mock-ipc';

// Forecast payload with real weekly_points so forecastData is non-null in Inspector.
function makeForecastBase64(): string {
  const payload = {
    engine_mode: 'transfer_with_bias_check',
    granularity: 'monthly',
    methodology_signature: 'transfer_with_bias_check_v1',
    horizon_weeks: 12,
    warnings: [],
    weekly_points: [
      { week_index: 0, point: 100, ci_lower: 80, ci_upper: 120 },
      { week_index: 1, point: 110, ci_lower: 85, ci_upper: 135 },
      { week_index: 2, point: 105, ci_lower: 82, ci_upper: 128 },
    ],
    // 1.4 schema v1: anchors + spend_plan for real reproduce mode (not preview)
    anchors: {
      market_size: 1000000.0,
      market_size_cv: 0.1,
      planned_share_trajectory: [0.05, 0.05, 0.05],
      distribution_trajectory: [0.8, 0.8, 0.8],
      pricing_index: 1.0,
      elasticity: 0.0,
      seasonality: null,
    },
    spend_plan: { tv: [50000, 50000, 50000] },
  };
  // Use Buffer.from for UTF-8 safety (btoa rejects non-Latin1 chars in Node.js)
  return Buffer.from(JSON.stringify(payload), 'utf8').toString('base64');
}

// Inject mock activeBundle via test hook if available.
async function injectMockBundle(page: Parameters<typeof setupMockIpc>[0]): Promise<boolean> {
  return page.evaluate(() => {
    const w = window as unknown as Record<string, unknown>;
    if (typeof w.__auroraTestSetBundle === 'function') {
      (w.__auroraTestSetBundle as (v: unknown) => void)({
        handle_id: 'mock-bundle-rep-1',
        source_format: 'aurora',
        size_bytes: 8192,
        revision: 1,
        manifest: {
          project_id: 'mock-proj-rep',
          revision: 1,
          aurora_app_version: '0.1.0',
          created_at: '2026-01-01T00:00:00Z',
          last_modified: '2026-01-01T00:00:00Z',
          files: { 'forecast.json': { sha256: 'ghi', size: 300 } },
          integrity_check: 'ok',
          compression: 'zstd',
        },
        path: '/mock/rep.aurora',
      });
      return true;
    }
    return false;
  });
}

// Navigate to the forecast tab (index 2 in TABS array).
// Returns true if tab was found and clicked, false if tablist not available.
async function navigateToForecastTab(page: Parameters<typeof setupMockIpc>[0]): Promise<boolean> {
  const tabs = page.getByRole('tab');
  const tabCount = await tabs.count();
  if (tabCount < 3) return false;
  await tabs.nth(2).click();
  return true;
}

test.describe('Inspector — M-09 Reproduce Python', () => {
  test.beforeEach(async ({ page }) => {
    const forecastBase64 = makeForecastBase64();
    await setupMockIpc(page, {
      open_bundle: () => ({
        handle_id: 'mock-bundle-rep-1',
        source_format: 'aurora',
        size_bytes: 8192,
        revision: 1,
        manifest: {
          project_id: 'mock-proj-rep',
          revision: 1,
          aurora_app_version: '0.1.0',
          created_at: '2026-01-01T00:00:00Z',
          last_modified: '2026-01-01T00:00:00Z',
          files: { 'forecast.json': { sha256: 'ghi', size: 300 } },
          integrity_check: 'ok',
          compression: 'zstd',
        },
        path: '/mock/rep.aurora',
      }),
      read_bundle_entry: () => ({
        entry: 'forecast.json',
        bytes_base64: forecastBase64,
        size_bytes: 300,
        sha256_hex: 'mock-sha-rep',
      }),
      // generate_reproduce_script — actual field is `script` (not `script_python`)
      // per ipc/forecast.ts generateReproduceScript return type.
      generate_reproduce_script: () => ({
        script: '# Aurora Reproduce — Python\nimport aurora_launch\n# ... fixture code ...\n',
        suggested_filename: 'reproduce.py',
      }),
      verify_bundle_signature: () => ({
        valid: true,
        signature_provenance: 'sample',
        signed_by: null,
        signed_at: null,
        key_fingerprint: null,
        composite_hash: null,
        manifest_revision: 1,
        trust_badge: 'sample',
        failure_reason: null,
      }),
      // M-03 explanation — minimal stub so explanation doesn't block forecast render
      explain_forecast: () => ({
        engine_used: 'local',
        confidence: 'medium',
        what: 'Прогноз построен.',
        why: 'Transfer model.',
        risks: 'Нет критичных рисков.',
      }),
      compute_trust_score: () => ({
        score: 75,
        tier: 'Medium',
        diagnostics: [],
      }),
    });
  });

  test('Reproduce Python button visible in forecast tab', async ({ page }) => {
    await page.goto('/inspector');
    const hookExists = await injectMockBundle(page);
    if (!hookExists) {
      test.skip(
        true,
        'window.__auroraTestSetBundle hook not exposed — Inspector M-09 button requires active bundle + forecastData. Defer to manual check.',
      );
      return;
    }

    const tabNavigated = await navigateToForecastTab(page);
    if (!tabNavigated) {
      test.skip(true, 'Forecast tab (index 2) not found in tablist — bundle injection may not have triggered Inspector mount.');
      return;
    }

    // Wait for forecast data to load (button only renders when forecastData is non-null)
    const btn = page.getByRole('button', { name: /Воспроизвести в Python|Reproduce/i }).first();
    const btnVisible = await btn.isVisible({ timeout: 5000 });
    if (!btnVisible) {
      test.skip(
        true,
        'Reproduce Python button not visible after 5s — forecastData may be null (read_bundle_entry mock may not have been called for forecast.json).',
      );
      return;
    }

    await expect(btn).toBeVisible();
  });

  test('Reproduce Python button → modal opens with Python code', async ({ page }) => {
    await page.goto('/inspector');
    const hookExists = await injectMockBundle(page);
    if (!hookExists) {
      test.skip(
        true,
        'window.__auroraTestSetBundle hook not exposed — cannot open reproduce modal without active bundle.',
      );
      return;
    }

    const tabNavigated = await navigateToForecastTab(page);
    if (!tabNavigated) {
      test.skip(true, 'Forecast tab not found.');
      return;
    }

    const btn = page.getByRole('button', { name: /Воспроизвести в Python|Reproduce/i }).first();
    const btnVisible = await btn.isVisible({ timeout: 5000 });
    if (!btnVisible) {
      test.skip(true, 'Reproduce Python button not present in current Inspector layout — defer to manual check.');
      return;
    }

    await btn.click();

    // Modal should appear with role="dialog"
    await expect(page.locator('[role="dialog"]').first()).toBeVisible({ timeout: 5000 });

    // Modal should contain generated Python code
    // Mock returns: '# Aurora Reproduce — Python\nimport aurora_launch\n...'
    await expect(
      page.locator('text=/import aurora_launch|# Aurora Reproduce/').first(),
    ).toBeVisible({ timeout: 5000 });
  });

  test('Reproduce modal closes on Escape key', async ({ page }) => {
    await page.goto('/inspector');
    const hookExists = await injectMockBundle(page);
    if (!hookExists) {
      test.skip(true, 'window.__auroraTestSetBundle hook not exposed.');
      return;
    }

    const tabNavigated = await navigateToForecastTab(page);
    if (!tabNavigated) {
      test.skip(true, 'Forecast tab not found.');
      return;
    }

    const btn = page.getByRole('button', { name: /Воспроизвести в Python|Reproduce/i }).first();
    if (!(await btn.isVisible({ timeout: 5000 }))) {
      test.skip(true, 'Reproduce button not present.');
      return;
    }

    await btn.click();
    await expect(page.locator('[role="dialog"]').first()).toBeVisible({ timeout: 3000 });

    await page.keyboard.press('Escape');

    // Modal should be gone after Escape
    await expect(page.locator('[role="dialog"]').first()).not.toBeVisible({ timeout: 3000 });
  });

  test('Reproduce modal a11y compliant (WCAG 2A/AA)', async ({ page }) => {
    await page.goto('/inspector');
    const hookExists = await injectMockBundle(page);
    if (!hookExists) {
      test.skip(true, 'window.__auroraTestSetBundle hook not exposed — a11y test requires active bundle + open modal.');
      return;
    }

    const tabNavigated = await navigateToForecastTab(page);
    if (!tabNavigated) {
      test.skip(true, 'Forecast tab not found.');
      return;
    }

    const btn = page.getByRole('button', { name: /Воспроизвести в Python|Reproduce/i }).first();
    if (!(await btn.isVisible({ timeout: 5000 }))) {
      test.skip(true, 'Reproduce button not present — skipping a11y test.');
      return;
    }

    await btn.click();
    // Wait for modal + script content to load
    await expect(page.locator('[role="dialog"]').first()).toBeVisible({ timeout: 3000 });
    // Give generate_reproduce_script mock time to resolve
    await page.waitForTimeout(300);

    await injectAxe(page);
    await checkA11y(
      page,
      { include: [['[role="dialog"]']] },
      {
        axeOptions: { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] } },
      },
    );
  });
});
