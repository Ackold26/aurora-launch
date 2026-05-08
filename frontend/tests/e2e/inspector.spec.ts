import { test, expect } from '@playwright/test';

test.describe('Inspector', () => {
  test('shows empty state when no bundle open', async ({ page }) => {
    await page.goto('/inspector');
    await expect(page.getByText(/empty|пуста/i)).toBeVisible();
  });
});
