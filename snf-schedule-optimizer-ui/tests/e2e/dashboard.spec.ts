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
  const monthlyResponse = page.waitForResponse((response) =>
    response.url().includes("/scheduling.v1.SchedulingService/GetMonthlySchedule"),
  );
  await page.goto("/schedule?tab=scheduling&view=timeline");
  expect((await monthlyResponse).ok()).toBeTruthy();

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

test("list schedule day card opens shift assignments without client errors", async ({ page }) => {
  const clientErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      clientErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    clientErrors.push(error.message);
  });

  await page.goto("/schedule?view=list");

  const populatedDayCard = page
    .getByTestId("schedule-day-card")
    .filter({ hasText: /\d+%/ })
    .first();

  await expect(page.getByRole("heading", { name: /master schedule/i })).toBeHidden();
  await expect(populatedDayCard).toBeVisible();

  await populatedDayCard.click();

  const shiftDialog = page.getByRole("dialog", { name: /schedule:/i });

  await expect(shiftDialog).toBeVisible();
  await expect(page.getByText(/nurses for .* shift/i)).toBeVisible();

  const assignedNurse = shiftDialog
    .locator("button")
    .filter({ hasText: /hrs/i, hasNotText: /required:/i })
    .first();

  await expect(assignedNurse).toBeVisible();
  await assignedNurse.click();

  await expect(shiftDialog.getByText(/shift control/i)).toBeVisible();

  expect(clientErrors).toEqual([]);
});

test("optimize flow updates the persisted schedule summary", async ({ page }) => {
  test.setTimeout(120_000);

  const optimizeResponse = page.waitForResponse((response) => {
    return response.url().includes("/scheduling.v1.SchedulingService/StartOptimizationRun");
  });
  const monthlyResponse = page.waitForResponse((response) =>
    response.url().includes("/scheduling.v1.SchedulingService/GetMonthlySchedule"),
  );

  await page.goto("/schedule?tab=scheduling&view=timeline");
  expect((await monthlyResponse).ok()).toBeTruthy();

  const optimizeButton = page.getByTestId("optimize-schedule");
  const summaryButton = page.getByTestId("open-schedule-summary");
  const facilitySummary = page.getByTestId("facility-summary");
  const scheduleLoadError = page.getByRole("heading", {
    name: /schedule data could not be loaded/i,
  });

  await expect(optimizeButton).toBeVisible();
  await expect(summaryButton).toBeVisible();
  await expect(scheduleLoadError).toBeHidden();
  await expect(facilitySummary).not.toContainText(/facility:\s*none/i);
  await expect(facilitySummary).not.toContainText(/loaded days:\s*0/i);

  await optimizeButton.click();
  const response = await optimizeResponse;
  expect(response.ok()).toBeTruthy();
  await expect(optimizeButton).toContainText(/optimizing/i);
  await expect(page.getByText(/run:/i)).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(/progress:/i)).toBeVisible({ timeout: 10000 });

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

  await expect(page.getByRole("button", { name: "Close Summary", exact: true })).toBeVisible();
});

test("persisted active run hydrates without mismatch", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });

  await page.addInitScript(() => {
    window.localStorage.setItem(
      "snf-scheduling-store",
      JSON.stringify({
        state: {
          draftState: {
            baseScheduleVersion: 1,
            patches: [],
            conflicts: [],
            hasPendingValidation: false,
          },
          activeRun: {
            runId: "persisted-run",
            scheduleId: "persisted-schedule",
            baseScheduleVersion: 1,
            resultScheduleVersion: null,
            status: "running",
            stage: "solving",
            progressPercent: 45,
            statusMessage: "Resuming persisted run",
            startedAt: "2026-05-13T12:00:00Z",
            completedAt: null,
            errorDetails: null,
            financials: null,
            stats: null,
            summary: null,
          },
        },
        version: 1,
      }),
    );
  });

  const monthlyResponse = page.waitForResponse((response) =>
    response.url().includes("/scheduling.v1.SchedulingService/GetMonthlySchedule"),
  );

  await page.goto("/schedule?tab=scheduling&view=timeline");
  expect((await monthlyResponse).ok()).toBeTruthy();

  const runPanel = page.locator("div.app-soft-panel").filter({
    hasText: /run:/i,
  }).last();

  await expect(runPanel).toContainText(/run:\s*solving/i);
  await expect(runPanel).toContainText(/progress:\s*45%/i);

  expect(
    consoleErrors.some((entry) => entry.includes("Hydration failed")),
  ).toBeFalsy();
  expect(
    consoleErrors.some((entry) => entry.includes("server rendered HTML didn't match the client")),
  ).toBeFalsy();
});
