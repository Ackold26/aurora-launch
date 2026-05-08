import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config для Aurora Launch E2E + a11y tests.
 *
 * Two main projects:
 * - `e2e` — full UX flow tests (wizard, inspector, compare, onboarding)
 * - `a11y` — WCAG AA + ГОСТ Р 52872-2019 axe-playwright runs
 *
 * Tests run против production-style build (npm run build → Tauri webview),
 * but без real Tauri runtime — webview-only с mocked IPC. Real native IPC
 * integration test smoke вызывается из CI на отдельной job.
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html'], ['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [
    {
      name: 'e2e',
      use: { ...devices['Desktop Chrome'] }
    },
    {
      name: 'a11y',
      testMatch: /.*\.a11y\.spec\.ts$/,
      use: { ...devices['Desktop Chrome'] }
    }
  ],
  webServer: {
    command: 'npm run dev',
    port: 5173,
    reuseExistingServer: !process.env.CI,
    timeout: 120000
  }
});
