import { test, expect } from "@playwright/test";

test("dashboard loads demo banner and scheduling module", async ({ page }) => {
  await page.goto("/schedule");

  await expect(page.getByTestId("demo-mode-banner")).toBeVisible();

  await expect(
    page.getByRole("tab", { name: /scheduling/i }),
  ).toBeVisible();

  await expect(
    page.getByRole("heading", { name: /scheduling/i }),
  ).toBeVisible();
});

test("landing page launches the interactive demo", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", {
      name: /make snf staffing feel predictable/i,
    }),
  ).toBeVisible();

  await page.getByRole("link", { name: /launch interactive demo/i }).click();
  await expect(page).toHaveURL(/\/schedule/);
});
