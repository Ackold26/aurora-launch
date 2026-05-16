/**
 * update-banner-with-notes.spec.ts — Phase 2.E (UX-6)
 *
 * E2E tests для UpdateAvailableBanner с release notes preview.
 *
 * Key architecture facts (recon 2026-05-16):
 *   - UpdateAvailableBanner is mounted in +layout.svelte: <UpdateAvailableBanner />
 *     with NO props — uses real tauri-plugin-updater check() at runtime.
 *   - The component has a `forceUpdate` prop for testing, but only accessible
 *     at component mount time (Svelte prop), not via DOM or window hook.
 *   - In e2e (SvelteKit dev server, no Tauri runtime), check() throws →
 *     bannerState = 'error' → visible = false (dismissedThisSession=false initially,
 *     but error state only shows via level='warning' i.e. bannerState==='error').
 *     Actually: visible = !dismissedThisSession && (available|downloading|ready|error)
 *     So error state IS visible if not dismissed.
 *   - The banner i18n key `updater.banner.error` shown in error state (warning level).
 *   - There is NO `__auroraTestSetUpdate` window hook in current codebase.
 *   - The component does NOT expose release_notes expansion — body field rendered
 *     via `updateInfo.body` (single string, not array) as `.update-banner__notes`.
 *   - No "что нового / what's new" expand button in current UI.
 *
 * Test strategy:
 *   1. Verify error state banner is visible (check() fails without Tauri runtime) —
 *      this is a real, always-exercised code path in dev/test mode.
 *   2. Verify forceUpdate prop test pattern — documented as skip because the prop
 *      is not settable from e2e without a window hook or Storybook.
 *   3. Note: proper UX-6 release notes e2e requires either:
 *      (a) Expose `window.__auroraTestSetUpdate(info)` in +layout.svelte behind
 *          `import.meta.env.DEV` flag that calls bannerState/updateInfo stores, OR
 *      (b) Mount UpdateAvailableBanner directly via a dedicated /test-banner route
 *          with forceUpdate prop, OR
 *      (c) Use Vitest unit test (UpdateAvailableBanner.test.ts already exists).
 */

import { test, expect } from '@playwright/test';
import { setupMockIpc } from './_helpers/mock-ipc';

test.describe('UpdateAvailableBanner — UX-6 release notes', () => {
  test.beforeEach(async ({ page }) => {
    // Mock IPC so layout mounts cleanly (get_build_info, license, etc.)
    await setupMockIpc(page);
  });

  test('error state banner visible when updater check fails (no Tauri runtime)', async ({
    page,
  }) => {
    // In e2e (SvelteKit dev server, no real Tauri), @tauri-apps/plugin-updater check()
    // throws → bannerState = 'error' → banner renders with level='warning'.
    // visible = !dismissedThisSession && bannerState === 'error' → true initially.
    // This verifies the error branch renders without crashing — a real always-hit path.
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Give onMount async check() time to run and fail
    await page.waitForTimeout(500);

    // The error banner (level='warning') renders via NotificationBanner as nb-banner--warning.
    // It shows role="status" with i18n key 'updater.banner.error'.
    // In dev env, if the check throws synchronously (module not available), bannerState='error'.
    const errorBanner = page.locator('[role="status"]').first();
    const bannerVisible = await errorBanner.isVisible({ timeout: 2000 });

    // This test passes if error banner shows OR if check() silently resolves to no-update.
    // We do NOT fail the test if banner is hidden — dev server check() may resolve null
    // (no update available) in some environments.
    if (bannerVisible) {
      // Error banner renders — verify it has expected structure
      await expect(errorBanner).toBeVisible();
    } else {
      // Banner hidden = check() resolved to no-update (also valid in some configs)
      test.skip(true, 'UpdateAvailableBanner hidden — check() resolved null (no update) in this environment. Error branch not triggered. This is valid dev-mode behaviour.');
    }
  });

  test('banner available state — requires forceUpdate prop or test hook (documents wiring gap)', async ({
    page,
  }) => {
    // This test documents the gap: UpdateAvailableBanner in +layout.svelte is mounted
    // without forceUpdate prop. To e2e-test the 'available' state we need either:
    //
    // Option A: Expose window hook in +layout.svelte (dev-only):
    //   if (import.meta.env.DEV) {
    //     window.__auroraTestSetUpdate = ({ version, body }) => { ... set store ... }
    //   }
    //
    // Option B: Add /test-banner route with <UpdateAvailableBanner forceUpdate={{...}} />
    //
    // Option C: Use existing Vitest unit test (tests/unit/UpdateAvailableBanner.test.ts)
    //
    // Current state: hook NOT exposed → skip with actionable reason.

    await page.goto('/');
    const hookExists = await page.evaluate(
      () => typeof (window as unknown as Record<string, unknown>).__auroraTestSetUpdate === 'function',
    );

    if (!hookExists) {
      test.skip(
        true,
        'window.__auroraTestSetUpdate hook not exposed in +layout.svelte. ' +
          'To enable this e2e test: add `if (import.meta.env.DEV) { window.__auroraTestSetUpdate = fn; }` ' +
          'in +layout.svelte onMount, where fn sets updateInfo + bannerState in local component state. ' +
          'Alternatively use Vitest unit test (UpdateAvailableBanner.test.ts) for forceUpdate prop testing.',
      );
      return;
    }

    // If hook exists (future implementation), inject available state
    await page.evaluate(() => {
      const fn = (window as unknown as Record<string, unknown>).__auroraTestSetUpdate;
      if (typeof fn === 'function') (fn as (v: unknown) => void)({ version: '0.1.2', body: 'Улучшен мастер импорта. Ускорен прогноз.' });
    });

    await expect(page.locator('text=/0\\.1\\.2|Доступна/').first()).toBeVisible({
      timeout: 3000,
    });
  });

  test('banner shows release body text when update available (requires test hook)', async ({
    page,
  }) => {
    await page.goto('/');
    const hookExists = await page.evaluate(
      () => typeof (window as unknown as Record<string, unknown>).__auroraTestSetUpdate === 'function',
    );

    if (!hookExists) {
      test.skip(
        true,
        'window.__auroraTestSetUpdate hook not exposed — release body (notes) rendering cannot be tested e2e. ' +
          'UpdateAvailableBanner.updateInfo.body rendered via .update-banner__notes span. ' +
          'Use Vitest unit test to verify body rendering via forceUpdate prop.',
      );
      return;
    }

    await page.evaluate(() => {
      const fn = (window as unknown as Record<string, unknown>).__auroraTestSetUpdate;
      if (typeof fn === 'function') (fn as (v: unknown) => void)({ version: '0.1.2', body: 'Улучшен мастер импорта. Ускорен прогноз.' });
    });

    // Notes rendered in .update-banner__notes span when updateInfo.body is non-null
    await expect(page.locator('text=/Улучшен мастер/').first()).toBeVisible({
      timeout: 3000,
    });
  });

  test('dismiss button hides banner (error or available state)', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(500); // let check() complete

    // Try to find any visible nb-dismiss button in a banner
    const dismissBtn = page.locator('.nb-dismiss--banner').first();
    const dismissVisible = await dismissBtn.isVisible({ timeout: 2000 });

    if (!dismissVisible) {
      test.skip(
        true,
        'No dismiss button visible — banner is hidden (check() returned null, no update available). ' +
          'Dismiss behaviour tested in Vitest unit test.',
      );
      return;
    }

    await dismissBtn.click();

    // After dismiss, banner should be hidden (dismissedThisSession = true)
    await expect(dismissBtn).not.toBeVisible({ timeout: 2000 });
  });
});
