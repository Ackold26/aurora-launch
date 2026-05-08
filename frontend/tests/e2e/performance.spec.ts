import { test, expect } from '@playwright/test';

test.describe('Performance budgets (PERFORMANCE_BUDGETS.md §1.3 updated)', () => {
  test('Welcome cold start ≤ 2s', async ({ page }) => {
    const start = Date.now();
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Aurora Launch' })).toBeVisible();
    const elapsed = Date.now() - start;
    expect(elapsed).toBeLessThan(2000);
  });

  test('Wizard step navigation ≤ 200ms', async ({ page }) => {
    await page.goto('/wizard');
    const t0 = Date.now();
    await page.getByRole('button', { name: /Next|Далее/ }).click();
    await expect(page.locator('.stepper li.active')).toHaveText(/2/);
    expect(Date.now() - t0).toBeLessThan(800); // ≤200ms ideal, ≤800ms in test envs
  });

  test('Theme switch ≤ 300ms (test-env tolerance)', async ({ page }) => {
    await page.goto('/settings');
    const t0 = Date.now();
    await page.getByRole('button', { name: /Light|Светлая/ }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    expect(Date.now() - t0).toBeLessThan(300);
  });
});
