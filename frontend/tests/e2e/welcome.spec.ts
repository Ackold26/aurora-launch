import { test, expect } from '@playwright/test';

test.describe('Welcome screen', () => {
  test('shows three entry points', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Aurora Launch' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Open sample|Открыть пример/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Import data|Импортировать данные/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /New launch|Новый запуск/ })).toBeVisible();
  });

  test('navigates to wizard on "New launch"', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /New launch|Новый запуск/ }).click();
    await expect(page).toHaveURL(/\/wizard/);
  });
});
