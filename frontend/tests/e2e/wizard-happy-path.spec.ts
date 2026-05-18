/**
 * wizard-happy-path.spec.ts
 *
 * Playwright E2E tests для Wizard flow (Phase 1.C).
 * IPC полностью замокан через mock-ipc.ts (window.__TAURI_INTERNALS__.invoke),
 * поэтому тесты работают против SvelteKit dev server без Tauri runtime.
 *
 * Покрытие:
 *   - 6 шагов stepper рендерится (mapping step удалён)
 *   - Step 1 (proxy) — 3 sample bundle карточки из мока list_sample_bundles
 *   - Step 2 (similarity) — кнопка Compute → SVG появляется
 *   - Step 3 (anchors) — 4 паттерна + слайдер intensity
 *   - Recovery dialog — показывается если draft с прогрессом
 *   - Recovery accept — восстанавливает step
 *   - Next/Back navigation — полный цикл туда-обратно
 *   - Back disabled на первом шаге
 */

import { test, expect } from '@playwright/test';
import { setupMockIpc } from './_helpers/mock-ipc';

// Helper: navigate to wizard with IPC already mocked.
// NOTE: setupMockIpc must be called before page.goto() — addInitScript
// registers a script executed on every new document load.
async function gotoWizard(page: Parameters<typeof setupMockIpc>[0]) {
  await page.goto('/wizard');
  // Wait for Svelte to hydrate — stepper is the first stable landmark.
  await expect(page.locator('.stepper')).toBeVisible({ timeout: 8000 });
}

// ─── Shared beforeEach ────────────────────────────────────────────────────────

test.describe('Wizard happy path (Phase 1.C)', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockIpc(page);
  });

  // ── Structural ──────────────────────────────────────────────────────────────

  test('renders all 6 steps в stepper', async ({ page }) => {
    await gotoWizard(page);
    await expect(page.locator('.stepper li')).toHaveCount(6);
  });

  test('Back disabled on first step', async ({ page }) => {
    await gotoWizard(page);
    await expect(page.getByRole('button', { name: /Back|Назад/ })).toBeDisabled();
  });

  // ── Step 1 (proxy) — sample bundles ────────────────────────────────────────

  test('Step 1 — ProxyPickerCard renders 3 sample bundles from mock', async ({ page }) => {
    await gotoWizard(page);
    // Next is gated behind previewHeaders.length > 0 when no file loaded,
    // but mock analyze_data_file auto-fills; we navigate with 1 click.
    // Since Next is disabled without a file, we skip straight from mock import.
    // For navigation test: use setupMockIpc override of wizard_session_load
    // with step=1 already set.
    await setupMockIpc(page, {
      wizard_session_load: () => ({
        session: {
          session_id: 'proxy-nav-test',
          step: 1,
          imported_file_path: '/mock/test.xlsx',
          imported_columns: ['date', 'sales_packs', 'tv_grp', 'competitor_share'],
          column_roles: [
            { name: 'date', role: 'date', confidence: 0.97, auto_detected: true },
          ],
          created_at: new Date().toISOString(),
          last_saved_at: new Date().toISOString(),
        },
      }),
    });
    await gotoWizard(page);
    // Accept recovery → jumps to step 1 (proxy)
    await page.getByRole('button', { name: /Восстановить/ }).click();
    // list_sample_bundles IPC is called by ProxyPickerCard onMount.
    // Labels come from defaultWizardHappyPathMocks.
    await expect(page.getByText('Кагоцел (грипп/ОРВИ)')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('Венарус (хроническая)')).toBeVisible();
    await expect(page.getByText('Мульти-прокси (3 бренда)')).toBeVisible();
  });

  // ── Step 2 (similarity) — Compute button ───────────────────────────────────

  test('Step 2 — Compute button → SVG radar appears', async ({ page }) => {
    await setupMockIpc(page, {
      wizard_session_load: () => ({
        session: {
          session_id: 'sim-nav-test',
          step: 2,
          imported_file_path: '/mock/test.xlsx',
          imported_columns: ['date', 'sales_packs'],
          column_roles: [],
          created_at: new Date().toISOString(),
          last_saved_at: new Date().toISOString(),
        },
      }),
    });
    await gotoWizard(page);
    await page.getByRole('button', { name: /Восстановить/ }).click();
    // Button text in wizard source: "Compute"
    await page.getByRole('button', { name: /Compute|Вычислить/ }).click();
    // RadarChart renders an SVG; wait for it to appear after IPC resolves
    await expect(page.locator('svg').first()).toBeVisible({ timeout: 5000 });
  });

  // ── Step 3 (anchors) — pattern picker ──────────────────────────────────────

  test('Step 3 — AnchorsForm pattern cards rendered', async ({ page }) => {
    await setupMockIpc(page, {
      wizard_session_load: () => ({
        session: {
          session_id: 'anchors-nav-test',
          step: 3,
          imported_file_path: '/mock/test.xlsx',
          imported_columns: ['date', 'sales_packs'],
          column_roles: [],
          created_at: new Date().toISOString(),
          last_saved_at: new Date().toISOString(),
        },
      }),
    });
    await gotoWizard(page);
    await page.getByRole('button', { name: /Восстановить/ }).click();
    // TRAJECTORY_PATTERNS label_ru values from trajectory_patterns.ts.
    // Each pattern is rendered as an aria-pressed button card.
    // 'Устойчивый рост' also appears in the subtitle text, so we target buttons.
    await expect(page.getByRole('button', { name: /Нарастание/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Устойчивый рост/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Снижение/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Свой график/ })).toBeVisible();
  });

  test('AnchorsForm — intensity slider visible by default (sustain pattern)', async ({
    page,
  }) => {
    await setupMockIpc(page, {
      wizard_session_load: () => ({
        session: {
          session_id: 'anchors-slider-test',
          step: 3,
          imported_file_path: '/mock/test.xlsx',
          imported_columns: ['date', 'sales_packs'],
          column_roles: [],
          created_at: new Date().toISOString(),
          last_saved_at: new Date().toISOString(),
        },
      }),
    });
    await gotoWizard(page);
    await page.getByRole('button', { name: /Восстановить/ }).click();
    // Intensity slider has aria-label="Интенсивность паттерна от 1 до 10"
    // Visible in all non-custom patterns (sustain is default).
    await expect(
      page.getByLabel(/Интенсивность паттерна/i),
    ).toBeVisible({ timeout: 3000 });
  });

  test('AnchorsForm — switching to custom pattern hides intensity slider', async ({
    page,
  }) => {
    await setupMockIpc(page, {
      wizard_session_load: () => ({
        session: {
          session_id: 'anchors-custom-test',
          step: 3,
          imported_file_path: '/mock/test.xlsx',
          imported_columns: ['date', 'sales_packs'],
          column_roles: [],
          created_at: new Date().toISOString(),
          last_saved_at: new Date().toISOString(),
        },
      }),
    });
    await gotoWizard(page);
    await page.getByRole('button', { name: /Восстановить/ }).click();
    // Slider visible in sustain (default)
    await expect(page.getByLabel(/Интенсивность паттерна/i)).toBeVisible();
    // Click «Свой график» pattern card — an aria-pressed button
    await page.getByRole('button', { name: /Свой график/ }).click();
    // Slider hidden in custom mode (AnchorsForm source: {#if safeDraft.pattern !== 'custom'})
    await expect(
      page.getByLabel(/Интенсивность паттерна/i),
    ).not.toBeVisible({ timeout: 2000 });
  });

  // ── Navigation ──────────────────────────────────────────────────────────────

  test('Next/Back navigation cycles through all 6 steps', async ({ page }) => {
    // Start at step 1 (proxy) via recovery to bypass file-upload gate on step 0
    await setupMockIpc(page, {
      wizard_session_load: () => ({
        session: {
          session_id: 'nav-cycle-test',
          step: 1,
          imported_file_path: '/mock/test.xlsx',
          imported_columns: ['date', 'sales_packs', 'tv_grp', 'competitor_share'],
          column_roles: [
            { name: 'date', role: 'date', confidence: 0.97, auto_detected: true },
          ],
          created_at: new Date().toISOString(),
          last_saved_at: new Date().toISOString(),
        },
      }),
    });
    await gotoWizard(page);
    await page.getByRole('button', { name: /Восстановить/ }).click();
    // Forward: step 2 → 6 (5 more clicks from step 1)
    for (let i = 1; i < 5; i++) {
      await page.getByRole('button', { name: /Next|Далее/ }).click();
      await expect(page.locator('.stepper li.active')).toContainText(
        String(i + 2),
      );
    }
    // Reverse: step 6 → 2
    for (let i = 4; i >= 1; i--) {
      await page.getByRole('button', { name: /Back|Назад/ }).click();
      await expect(page.locator('.stepper li.active')).toContainText(
        String(i + 1),
      );
    }
  });

  // ── Recovery dialog ─────────────────────────────────────────────────────────

  test('Recovery dialog shown when session draft with progress exists', async ({
    page,
  }) => {
    // Override wizard_session_load with a recoverable draft (step > 0 + file)
    await setupMockIpc(page, {
      wizard_session_load: () => ({
        session: {
          session_id: 'test-recovery-show-1',
          step: 3,
          imported_file_path: '/mock/test.xlsx',
          imported_columns: ['date', 'sales_packs', 'tv_grp'],
          column_roles: [
            { name: 'date', role: 'date', confidence: 0.97, auto_detected: true },
            { name: 'sales_packs', role: 'kpi', confidence: 0.85, auto_detected: true },
          ],
          validation_done: true,
          selected_proxy_path: '/mock/kagotsel.aurora',
          selected_proxy_label: 'Кагоцел',
          created_at: new Date(Date.now() - 3600000).toISOString(),
          last_saved_at: new Date(Date.now() - 1800000).toISOString(),
        },
      }),
    });
    await gotoWizard(page);
    // Recovery dialog title from wizard source: "Восстановить незаконченный сеанс?"
    await expect(
      page.getByText(/Восстановить незаконченный сеанс/),
    ).toBeVisible({ timeout: 4000 });
    await expect(page.getByRole('button', { name: /Восстановить/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Начать заново/ })).toBeVisible();
  });

  test('Recovery dialog — accept restores to saved step', async ({ page }) => {
    await setupMockIpc(page, {
      wizard_session_load: () => ({
        session: {
          session_id: 'test-recovery-accept-2',
          step: 2,
          imported_file_path: '/mock/test.xlsx',
          imported_columns: ['date', 'sales_packs'],
          column_roles: [],
          validation_done: false,
          created_at: new Date().toISOString(),
          last_saved_at: new Date().toISOString(),
        },
      }),
    });
    await gotoWizard(page);
    // Click Restore
    await page.getByRole('button', { name: /Восстановить/ }).click();
    // After recovery: step should be 2 (0-indexed), so stepper shows "3"
    await expect(page.locator('.stepper li.active')).toContainText('3', {
      timeout: 3000,
    });
  });

  test('Recovery dialog — dismiss starts fresh (step 1)', async ({ page }) => {
    await setupMockIpc(page, {
      wizard_session_load: () => ({
        session: {
          session_id: 'test-recovery-dismiss-3',
          step: 4,
          imported_file_path: '/mock/test.xlsx',
          imported_columns: ['date', 'sales_packs'],
          column_roles: [],
          validation_done: false,
          created_at: new Date().toISOString(),
          last_saved_at: new Date().toISOString(),
        },
      }),
    });
    await gotoWizard(page);
    await page.getByRole('button', { name: /Начать заново/ }).click();
    // After dismiss: back to step 1
    await expect(page.locator('.stepper li.active')).toContainText('1', {
      timeout: 3000,
    });
  });
});
