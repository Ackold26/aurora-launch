import { test, expect } from '@playwright/test';

test.describe('In-app feedback (Cmd+Shift+F)', () => {
  test('opens overlay on shortcut', async ({ page }) => {
    await page.goto('/');
    const isMac = process.platform === 'darwin';
    const mod = isMac ? 'Meta' : 'Control';
    await page.keyboard.press(`${mod}+Shift+F`);
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByText(/Feedback|Обратная связь/)).toBeVisible();
  });

  test('Esc closes overlay', async ({ page }) => {
    await page.goto('/');
    const isMac = process.platform === 'darwin';
    const mod = isMac ? 'Meta' : 'Control';
    await page.keyboard.press(`${mod}+Shift+F`);
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });
});
