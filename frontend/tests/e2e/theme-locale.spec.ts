import { test, expect } from '@playwright/test';

test.describe('Theme + locale switching', () => {
  test('cycles dark → light via Settings', async ({ page }) => {
    await page.goto('/settings');
    await page.getByRole('button', { name: /Light|Светлая/ }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    await page.getByRole('button', { name: /Dark|Тёмная/ }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  });

  test('high-contrast mode for a11y', async ({ page }) => {
    await page.goto('/settings');
    await page.getByRole('button', { name: /High contrast|Высокий контраст/ }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'high-contrast');
  });

  test('locale switch updates UI strings', async ({ page }) => {
    await page.goto('/settings');
    await page.getByRole('button', { name: 'EN' }).click();
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
    await page.getByRole('button', { name: 'RU' }).click();
    await expect(page.getByRole('heading', { name: 'Настройки' })).toBeVisible();
  });
});
