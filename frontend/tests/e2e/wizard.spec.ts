import { test, expect } from '@playwright/test';

test.describe('Wizard flow', () => {
  test('renders all 7 steps в stepper', async ({ page }) => {
    await page.goto('/wizard');
    const steps = await page.locator('.stepper li').count();
    expect(steps).toBe(7);
  });

  test('Next/Back navigation moves step indicator', async ({ page }) => {
    await page.goto('/wizard');
    await expect(page.locator('.stepper li.active')).toHaveText(/1/);
    await page.getByRole('button', { name: /Next|Далее/ }).click();
    await expect(page.locator('.stepper li.active')).toHaveText(/2/);
    await page.getByRole('button', { name: /Back|Назад/ }).click();
    await expect(page.locator('.stepper li.active')).toHaveText(/1/);
  });

  test('Back disabled on first step', async ({ page }) => {
    await page.goto('/wizard');
    await expect(page.getByRole('button', { name: /Back|Назад/ })).toBeDisabled();
  });
});
