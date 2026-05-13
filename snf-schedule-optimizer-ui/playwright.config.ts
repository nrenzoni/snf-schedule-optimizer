import { defineConfig, devices } from "@playwright/test";

if (!process.env.PLAYWRIGHT_BASE_URL) {
  throw new Error("Missing PLAYWRIGHT_BASE_URL for Playwright E2E runs.");
}

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  expect: {
    timeout: 10000,
  },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL,
    testIdAttribute: "data-testid",
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
        use: { ...devices["Desktop Chrome"] },
    },
  ],
});
