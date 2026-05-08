import { test, expect } from '@playwright/test';

test.describe('Compare page', () => {
  test('renders demo proxy slots', async ({ page }) => {
    await page.goto('/compare');
    await expect(page.getByText(/Proxy A/)).toBeVisible();
    await expect(page.getByText(/Proxy B/)).toBeVisible();
  });

  test('add slot increases count', async ({ page }) => {
    await page.goto('/compare');
    const before = await page.locator('article.card, button.card').count();
    await page.getByRole('button', { name: /Add proxy|Добавить proxy/ }).click();
    const after = await page.locator('article.card, button.card').count();
    expect(after).toBeGreaterThan(before);
  });
});
