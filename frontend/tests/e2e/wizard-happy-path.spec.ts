/**
 * wizard-happy-path.spec.ts
 *
 * Playwright E2E tests для Wizard flow (Phase 1.C).
 * IPC полностью замокан через mock-ipc.ts (window.__TAURI_INTERNALS__.invoke),
 * поэтому тесты работают против SvelteKit dev server без Tauri runtime.
 *
 * Покрытие:
 *   - 7 шагов stepper рендерится
 *   - Step 1 (mapping) — hint «сначала импортируйте» при отсутствии данных
 *   - Step 2 (proxy) — 3 sample bundle карточки из мока list_sample_bundles
 *   - Step 3 (similarity) — кнопка Compute → SVG появляется
 *   - Step 4 (anchors) — 4 паттерна + слайдер intensity
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

  test('renders all 7 steps в stepper', async ({ page }) => {
    await gotoWizard(page);
    await expect(page.locator('.stepper li')).toHaveCount(7);
  });

  test('Back disabled on first step', async ({ page }) => {
    await gotoWizard(page);
    await expect(page.getByRole('button', { name: /Back|Назад/ })).toBeDisabled();
  });

  // ── Step 1 (mapping) — empty hint ──────────────────────────────────────────

  test('Step 1 — empty mapping hint visible without import', async ({ page }) => {
    await gotoWizard(page);
    await page.getByRole('button', { name: /Next|Далее/ }).click();
    // Wizard source: "Сначала импортируйте файл на предыдущем шаге..."
    await expect(
      page.getByText(/Сначала импортируйте файл/),
    ).toBeVisible({ timeout: 3000 });
  });

  // ── Step 2 (proxy) — sample bundles ────────────────────────────────────────

  test('Step 2 — ProxyPickerCard renders 3 sample bundles from mock', async ({ page }) => {
    await gotoWizard(page);
    for (let i = 0; i < 2; i++) {
      await page.getByRole('button', { name: /Next|Далее/ }).click();
    }
    // list_sample_bundles IPC is called by ProxyPickerCard onMount.
    // Labels come from defaultWizardHappyPathMocks.
    await expect(page.getByText('Кагоцел (грипп/ОРВИ)')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('Венарус (хроническая)')).toBeVisible();
    await expect(page.getByText('Мульти-прокси (3 бренда)')).toBeVisible();
  });

  // ── Step 3 (similarity) — Compute button ───────────────────────────────────

  test('Step 3 — Compute button → SVG radar appears', async ({ page }) => {
    await gotoWizard(page);
    for (let i = 0; i < 3; i++) {
      await page.getByRole('button', { name: /Next|Далее/ }).click();
    }
    // Button text in wizard source: "Compute"
    await page.getByRole('button', { name: /Compute|Вычислить/ }).click();
    // RadarChart renders an SVG; wait for it to appear after IPC resolves
    await expect(page.locator('svg').first()).toBeVisible({ timeout: 5000 });
  });

  // ── Step 4 (anchors) — pattern picker ──────────────────────────────────────

  test('Step 4 — AnchorsForm pattern cards rendered', async ({ page }) => {
    await gotoWizard(page);
    for (let i = 0; i < 4; i++) {
      await page.getByRole('button', { name: /Next|Далее/ }).click();
    }
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
    await gotoWizard(page);
    for (let i = 0; i < 4; i++) {
      await page.getByRole('button', { name: /Next|Далее/ }).click();
    }
    // Intensity slider has aria-label="Интенсивность паттерна от 1 до 10"
    // Visible in all non-custom patterns (sustain is default).
    await expect(
      page.getByLabel(/Интенсивность паттерна/i),
    ).toBeVisible({ timeout: 3000 });
  });

  test('AnchorsForm — switching to custom pattern hides intensity slider', async ({
    page,
  }) => {
    await gotoWizard(page);
    for (let i = 0; i < 4; i++) {
      await page.getByRole('button', { name: /Next|Далее/ }).click();
    }
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

  test('Next/Back navigation cycles through all 7 steps', async ({ page }) => {
    await gotoWizard(page);
    // Forward: step 1 → 7
    for (let i = 0; i < 6; i++) {
      await page.getByRole('button', { name: /Next|Далее/ }).click();
      await expect(page.locator('.stepper li.active')).toContainText(
        String(i + 2),
      );
    }
    // Reverse: step 7 → 1
    for (let i = 5; i >= 0; i--) {
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
          imported_adapter_id: 'dsm_v2024',
          imported_record_count: 100,
          imported_columns: ['Бренд', 'Дата'],
          column_mapping: [{ source_column: 'Бренд', canonical_field: 'brand_name' }],
          mapping_done: true,
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
          imported_adapter_id: 'dsm_v2024',
          imported_record_count: 100,
          imported_columns: ['Бренд', 'Дата'],
          column_mapping: [],
          mapping_done: false,
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
          imported_adapter_id: 'dsm_v2024',
          imported_record_count: 50,
          imported_columns: ['Бренд'],
          column_mapping: [],
          mapping_done: false,
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
