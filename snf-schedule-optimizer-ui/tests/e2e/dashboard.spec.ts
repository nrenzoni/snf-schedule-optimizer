import { test, expect } from "@playwright/test";

test("dashboard loads inline demo mode header and scheduling module", async ({ page }) => {
  await page.goto("/schedule");

  await expect(page.getByRole("heading", { name: /staffing command center/i })).toBeVisible();
  await expect(page.getByTestId("dashboard-demo-mode")).toBeVisible();
  await expect(page.getByTestId("facility-summary")).toContainText(/loaded days:/i);

  await expect(
    page.getByRole("tab", { name: /scheduling/i }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: /scheduling/i })).toHaveAttribute(
    "data-state",
    "active",
  );
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

test("scheduling toolbar stays shared across list and timeline", async ({ page }) => {
  await page.goto("/schedule?tab=scheduling&view=timeline");

  const timelineButton = page.getByTestId("view-timeline");
  const listButton = page.getByTestId("view-list");
  const optimizeButton = page.getByTestId("optimize-schedule");
  const summaryButton = page.getByTestId("open-schedule-summary");
  const configButton = page.getByTestId("open-scheduling-config");
  const masterScheduleHeading = page.getByRole("heading", { name: /master schedule/i });

  await expect(optimizeButton).toBeVisible();
  await expect(summaryButton).toBeVisible();
  await expect(configButton).toBeVisible();
  await expect(masterScheduleHeading).toBeVisible();

  const timelineWidth = await masterScheduleHeading.evaluate((node) => {
    return Math.round(node.getBoundingClientRect().width);
  });

  await summaryButton.click();
  await expect(page.getByRole("heading", { name: /monthly schedule summary/i })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: /monthly schedule summary/i })).toBeHidden();

  await configButton.click();
  await expect(page.getByRole("heading", { name: /scheduler configuration/i })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: /scheduler configuration/i })).toBeHidden();

  await listButton.click();
  await expect(page).toHaveURL(/view=list/);
  await expect(optimizeButton).toBeVisible();
  await expect(summaryButton).toBeVisible();
  await expect(configButton).toBeVisible();

  const listCard = page.locator("div.app-card").filter({ has: page.getByText(/current facility:/i) }).first();
  await expect(listCard).toBeVisible();

  await timelineButton.click();
  await expect(page).toHaveURL(/\/schedule\?tab=scheduling(?:&view=timeline)?$/);
  await expect(masterScheduleHeading).toBeVisible();

  const timelineWidthAfterSwitch = await masterScheduleHeading.evaluate((node) => {
    return Math.round(node.getBoundingClientRect().width);
  });

  expect(Math.abs(timelineWidthAfterSwitch - timelineWidth)).toBeLessThanOrEqual(1);

  const scheduleArea = page.locator("div.app-card").filter({ has: masterScheduleHeading }).first();
  const staffMixCard = page.getByText("Staff Mix").locator("..").locator("..");
  const scheduleBottom = await scheduleArea.evaluate((node) => node.getBoundingClientRect().bottom);
  const staffMixTop = await staffMixCard.evaluate((node) => node.getBoundingClientRect().top);

  expect(staffMixTop).toBeGreaterThan(scheduleBottom);
});

test("optimize flow updates the persisted schedule summary", async ({ page }) => {
  test.setTimeout(120_000);

  await page.goto("/schedule?tab=scheduling&view=timeline");

  const optimizeButton = page.getByTestId("optimize-schedule");
  const summaryButton = page.getByTestId("open-schedule-summary");
  const facilitySummary = page.getByTestId("facility-summary");
  const scheduleLoadError = page.getByRole("heading", {
    name: /schedule data could not be loaded/i,
  });
  const optimizeResponse = page.waitForResponse((response) => {
    return response.url().includes("/scheduling.v1.SchedulingService/OptimizeSchedule");
  });

  await expect(optimizeButton).toBeVisible();
  await expect(summaryButton).toBeVisible();
  await expect(scheduleLoadError).toBeHidden();
  await expect(facilitySummary).not.toContainText(/facility:\s*none/i);
  await expect(facilitySummary).not.toContainText(/loaded days:\s*0/i);

  await optimizeButton.click();
  const response = await optimizeResponse;
  expect(response.ok()).toBeTruthy();
  await expect(optimizeButton).toBeEnabled({ timeout: 60000 });
  await expect(optimizeButton).toContainText(/^optimize$/i);

  await summaryButton.click();

  await expect(page.getByRole("heading", { name: /monthly schedule summary/i })).toBeVisible();
  await expect(page.getByText(/latest run:/i)).not.toContainText(/no optimization completed yet/i);
  await expect(page.getByText(/runtime/i)).toBeVisible();
  await expect(page.getByText(/objective/i)).toBeVisible();
  await expect(page.getByText(/variables/i)).toBeVisible();
  await expect(page.getByText(/constraints/i)).toBeVisible();

  const latestRunText = await page.getByText(/latest run:/i).textContent();
  expect(latestRunText).toBeTruthy();
  expect(latestRunText).not.toMatch(/no optimization completed yet/i);

  await expect(page.getByRole("button", { name: /close summary/i })).toBeVisible();
});
