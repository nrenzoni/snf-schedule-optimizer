import { test, expect } from "@playwright/test";

test("dashboard loads demo banner and scheduling module", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", {
      name: /explore scheduling, scenarios, and forecasts/i,
    }),
  ).toBeVisible();

  await expect(
    page.getByRole("tab", { name: /scheduling/i }),
  ).toBeVisible();

  await expect(page.getByText(/demo mode/i)).toBeVisible();
});
