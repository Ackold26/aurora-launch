import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';

test.describe('Accessibility (WCAG AA + ГОСТ Р 52872-2019)', () => {
  test('Welcome page has no critical/serious violations', async ({ page }) => {
    await page.goto('/');
    await injectAxe(page);
    await checkA11y(page, undefined, {
      detailedReport: true,
      detailedReportOptions: { html: true },
      axeOptions: { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } }
    });
  });

  test('Wizard page has no critical/serious violations', async ({ page }) => {
    await page.goto('/wizard');
    await injectAxe(page);
    await checkA11y(page, undefined, {
      axeOptions: { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } }
    });
  });

  test('Inspector empty state has no critical/serious violations', async ({ page }) => {
    await page.goto('/inspector');
    await injectAxe(page);
    await checkA11y(page, undefined, {
      axeOptions: { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } }
    });
  });

  test('Settings has no critical/serious violations', async ({ page }) => {
    await page.goto('/settings');
    await injectAxe(page);
    await checkA11y(page, undefined, {
      axeOptions: { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } }
    });
  });

  test('History has no critical/serious violations', async ({ page }) => {
    await page.goto('/history');
    await injectAxe(page);
    await checkA11y(page, undefined, {
      axeOptions: { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } }
    });
  });
});
