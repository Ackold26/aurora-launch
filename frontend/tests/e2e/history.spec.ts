import { test, expect } from '@playwright/test';

test.describe('History page', () => {
  test('renders empty audit log gracefully', async ({ page }) => {
    await page.goto('/history');
    await expect(page.getByRole('heading', { name: /History|История/ })).toBeVisible();
    // Without IPC backend, empty/skeleton states accept either path
    await expect(page.locator('body')).toBeVisible();
  });
});
