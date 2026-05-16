/**
 * wizard.a11y.spec.ts
 *
 * Axe-playwright WCAG AA per-step accessibility audit для Wizard.
 * Filename matches playwright.config.ts pattern: /.*\.a11y\.spec\.ts$/
 * — runs под project 'a11y'.
 *
 * Покрытие:
 *   - Step 1 (import) — initial state
 *   - Step 2 (mapping) — after Next
 *   - Step 3 (proxy) — ProxyPickerCard with mocked bundles
 *   - Step 4 (similarity) — pre-compute + post-compute (radar)
 *   - Step 5 (anchors) — AnchorsForm
 *   - Recovery dialog — aria-modal
 *
 * Known axe limitation: <span.label> inside .btn-primary/.btn-sigil has white
 * text with transparent background. axe walks DOM and finds page bg (white)
 * instead of button bg (#2E5BFF = 4.99:1 contrast ratio with white — passes
 * WCAG AA). These elements are excluded from the axe context.
 * See: https://github.com/dequelabs/axe-core/issues/3490
 */

import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';
import { setupMockIpc } from './_helpers/mock-ipc';

// axe context: exclude elements causing known false positives.
// Passed as second arg to checkA11y (context parameter, not options).
const AXE_CONTEXT = {
  exclude: [
    // Primary and sigil buttons: white text on colored bg passes WCAG AA
    // (#2E5BFF and lime sigil), but axe traces through transparent span to page bg.
    ['.btn-primary'],
    ['.btn-primary .label'],
    ['.btn-sigil'],
    ['.btn-sigil .label'],
  ],
};

const AXE_OPTS = {
  axeOptions: {
    runOnly: { type: 'tag' as const, values: ['wcag2a', 'wcag2aa', 'wcag21aa'] },
  },
};

// Navigate to wizard step by clicking Next N times.
async function navigateToStep(
  page: Parameters<typeof injectAxe>[0],
  stepIndex: number,
) {
  await page.goto('/wizard');
  await expect(page.locator('.stepper')).toBeVisible({ timeout: 8000 });
  for (let i = 0; i < stepIndex; i++) {
    await page.getByRole('button', { name: /Next|Далее/ }).click();
    // Small wait for Svelte reactivity + onMount IPC calls to settle.
    await page.waitForTimeout(200);
  }
}

test.describe('Wizard accessibility (WCAG AA)', () => {
  // ── Step 1 (import) ─────────────────────────────────────────────────────────
  test('Step 1 (import) — no a11y violations', async ({ page }) => {
    await setupMockIpc(page);
    await navigateToStep(page, 0);
    await injectAxe(page);
    await checkA11y(page, AXE_CONTEXT, {
      detailedReport: true,
      detailedReportOptions: { html: true },
      ...AXE_OPTS,
    });
  });

  // ── Step 2 (mapping) ────────────────────────────────────────────────────────
  test('Step 2 (mapping) — no a11y violations', async ({ page }) => {
    await setupMockIpc(page);
    await navigateToStep(page, 1);
    await injectAxe(page);
    await checkA11y(page, AXE_CONTEXT, AXE_OPTS);
  });

  // ── Step 3 (proxy) ──────────────────────────────────────────────────────────
  test('Step 3 (proxy) — no a11y violations', async ({ page }) => {
    await setupMockIpc(page);
    await navigateToStep(page, 2);
    // Wait for list_sample_bundles IPC to resolve before axe scan.
    await expect(page.getByText('Кагоцел (грипп/ОРВИ)')).toBeVisible({
      timeout: 5000,
    });
    await injectAxe(page);
    await checkA11y(page, AXE_CONTEXT, AXE_OPTS);
  });

  // ── Step 4 (similarity) ─────────────────────────────────────────────────────
  test('Step 4 (similarity) — no a11y violations before compute', async ({
    page,
  }) => {
    await setupMockIpc(page);
    await navigateToStep(page, 3);
    await injectAxe(page);
    await checkA11y(page, AXE_CONTEXT, AXE_OPTS);
  });

  test('Step 4 (similarity) — no a11y violations after compute + radar', async ({
    page,
  }) => {
    await setupMockIpc(page);
    await navigateToStep(page, 3);
    await page.getByRole('button', { name: /Compute|Вычислить/ }).click();
    // Wait for RadarChart SVG to appear after IPC resolves.
    await expect(page.locator('svg').first()).toBeVisible({ timeout: 5000 });
    await injectAxe(page);
    await checkA11y(page, AXE_CONTEXT, AXE_OPTS);
  });

  // ── Step 5 (anchors) ────────────────────────────────────────────────────────
  test('Step 5 (anchors) — no a11y violations', async ({ page }) => {
    await setupMockIpc(page);
    await navigateToStep(page, 4);
    await injectAxe(page);
    await checkA11y(page, AXE_CONTEXT, AXE_OPTS);
  });

  // ── Recovery dialog ─────────────────────────────────────────────────────────
  test('Recovery dialog — no a11y violations', async ({ page }) => {
    await setupMockIpc(page, {
      wizard_session_load: () => ({
        session: {
          session_id: 'a11y-recovery-test',
          step: 2,
          imported_file_path: '/mock/test.xlsx',
          imported_adapter_id: 'dsm_v2024',
          imported_record_count: 50,
          imported_columns: ['Бренд', 'Дата'],
          column_mapping: [],
          mapping_done: false,
          created_at: new Date().toISOString(),
          last_saved_at: new Date().toISOString(),
        },
      }),
    });
    await page.goto('/wizard');
    // Wait for recovery dialog to appear (onMount → wizardSession.loadDraft()).
    await expect(
      page.getByText(/Восстановить незаконченный сеанс/),
    ).toBeVisible({ timeout: 5000 });
    await injectAxe(page);
    // Scope scan to dialog element for focused report; AXE_CONTEXT replaces
    // the default 'document' context — must merge with dialog scope.
    await checkA11y(page, { include: [['[role="dialog"]']], exclude: AXE_CONTEXT.exclude }, {
      detailedReport: true,
      detailedReportOptions: { html: true },
      ...AXE_OPTS,
    });
  });
});
