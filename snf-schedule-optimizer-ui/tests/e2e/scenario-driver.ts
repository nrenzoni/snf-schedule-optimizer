import { expect, chromium, type BrowserContext, type ConsoleMessage, type Page } from "@playwright/test";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

type ScenarioAction =
  | "goto"
  | "hover_test_id"
  | "click_role"
  | "click_test_id"
  | "expect_role"
  | "expect_test_id"
  | "expect_text"
  | "wait_for_url"
  | "sleep";

interface ScenarioStep {
  name: string;
  action: ScenarioAction;
  url?: string;
  role?: string;
  namePattern?: string;
  testId?: string;
  text?: string;
  pattern?: string;
  timeoutMs?: number;
  durationMs?: number;
}

interface ScenarioDefinition {
  name: string;
  description: string;
  steps: ScenarioStep[];
}

interface FailureRecord {
  type: string;
  message: string;
  step?: string;
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

const runId = requireEnv("E2E_RUN_ID");
const baseUrl = requireEnv("E2E_BASE_URL");
const artifactsDir = requireEnv("E2E_ARTIFACTS_DIR");
const scenarioPath = requireEnv("E2E_SCENARIO_PATH");

const browserArtifactsDir = artifactsDir;
const eventsPath = path.join(browserArtifactsDir, "events.jsonl");
const summaryPath = path.join(browserArtifactsDir, "summary.json");
const tracePath = path.join(browserArtifactsDir, "trace.zip");

const failures: FailureRecord[] = [];
const events: Array<Record<string, unknown>> = [];

async function loadScenario(): Promise<ScenarioDefinition> {
  const scenarioModule = await import(pathToFileURL(scenarioPath).href, {
    with: { type: "json" },
  });
  return scenarioModule.default as ScenarioDefinition;
}

async function appendEvent(event: Record<string, unknown>) {
  events.push(event);
}

function severityForConsole(msg: ConsoleMessage) {
  if (msg.type() === "error") {
    return "high";
  }
  if (msg.type() === "warning") {
    return "low";
  }
  return null;
}

function isIgnorableConsoleError(message: string) {
  return message.includes("/_next/webpack-hmr") && message.includes("ERR_CONNECTION_REFUSED");
}

function recordFailure(type: string, message: string, step?: string) {
  failures.push({ type, message, step });
}

function roleLocator(page: Page, step: ScenarioStep) {
  if (!step.role || !step.namePattern) {
    throw new Error(`Step '${step.name}' requires role and namePattern.`);
  }
  return page.getByRole(step.role as never, {
    name: new RegExp(step.namePattern, "i"),
  });
}

async function executeStep(page: Page, step: ScenarioStep) {
  switch (step.action) {
    case "goto":
      await page.goto(step.url ?? "/", { waitUntil: "networkidle" });
      break;
    case "hover_test_id":
      await page.getByTestId(step.testId ?? "").hover();
      break;
    case "click_role":
      await roleLocator(page, step).click();
      break;
    case "click_test_id":
      await page.getByTestId(step.testId ?? "").click();
      break;
    case "expect_role":
      await expect(roleLocator(page, step)).toBeVisible({ timeout: step.timeoutMs ?? 10000 });
      break;
    case "expect_test_id":
      await expect(page.getByTestId(step.testId ?? "")).toBeVisible({ timeout: step.timeoutMs ?? 10000 });
      break;
    case "expect_text":
      await expect(page.getByText(step.text ?? "", { exact: false })).toBeVisible({ timeout: step.timeoutMs ?? 10000 });
      break;
    case "wait_for_url":
      await page.waitForURL(new RegExp(step.pattern ?? ".*"), { timeout: step.timeoutMs ?? 10000 });
      break;
    case "sleep":
      await page.waitForTimeout(step.durationMs ?? 1000);
      break;
    default:
      throw new Error(`Unsupported action: ${step.action}`);
  }
}

async function main() {
  await mkdir(browserArtifactsDir, { recursive: true });
  const scenario = await loadScenario();

  const browser = await chromium.launch();
  const context: BrowserContext = await browser.newContext({
    baseURL: baseUrl,
    extraHTTPHeaders: {
      "x-e2e-run-id": runId,
    },
  });
  const page = await context.newPage();
  await context.tracing.start({ screenshots: true, snapshots: true });

  page.on("pageerror", (error) => {
    recordFailure("pageerror", error.message);
  });

  page.on("console", (message) => {
    if (message.type() === "error" && isIgnorableConsoleError(message.text())) {
      void appendEvent({
        kind: "console.ignored",
        severity: "low",
        text: message.text(),
        type: message.type(),
        url: page.url(),
        timestamp: new Date().toISOString(),
      });
      return;
    }

    const severity = severityForConsole(message);
    void appendEvent({
      kind: "console",
      severity,
      text: message.text(),
      type: message.type(),
      url: page.url(),
      timestamp: new Date().toISOString(),
    });
    if (message.type() === "error") {
      recordFailure("console", message.text());
    }
  });

  page.on("requestfailed", (request) => {
    const message = `${request.method()} ${request.url()} failed: ${request.failure()?.errorText ?? "unknown"}`;
    recordFailure("requestfailure", message);
    void appendEvent({
      kind: "requestfailed",
      message,
      timestamp: new Date().toISOString(),
    });
  });

  page.on("response", (response) => {
    const request = response.request();
    const url = response.url();
    const isApiCall = url.includes("/scheduling.v1.SchedulingService") || url.includes("/health");
    if (isApiCall && response.status() >= 400) {
      recordFailure(
        "response",
        `${request.method()} ${url} returned ${response.status()}`,
      );
    }
  });

  let status = "passed";
  let failingStep: string | null = null;

  try {
    for (const step of scenario.steps) {
      await appendEvent({
        kind: "step.started",
        name: step.name,
        action: step.action,
        url: page.url(),
        timestamp: new Date().toISOString(),
      });

      try {
        await executeStep(page, step);
        await appendEvent({
          kind: "step.passed",
          name: step.name,
          action: step.action,
          url: page.url(),
          timestamp: new Date().toISOString(),
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        recordFailure("step_failure", message, step.name);
        await appendEvent({
          kind: "step.failed",
          name: step.name,
          action: step.action,
          url: page.url(),
          message,
          timestamp: new Date().toISOString(),
        });
        failingStep = step.name;
        status = "failed";
        break;
      }
    }

    if (failures.length > 0) {
      status = "failed";
    }
  } finally {
    if (status === "failed") {
      await page.screenshot({ path: path.join(browserArtifactsDir, "failure.png"), fullPage: true });
    }

    await context.tracing.stop({ path: tracePath });
    await browser.close();
  }

  await writeFile(
    eventsPath,
    events.map((event) => JSON.stringify(event)).join("\n") + (events.length > 0 ? "\n" : ""),
    "utf-8",
  );

  await writeFile(
    summaryPath,
    JSON.stringify(
      {
        status,
        runId,
        scenario: scenario.name,
        failingStep,
        failures,
        artifacts: {
          trace: "trace.zip",
          screenshot: status === "failed" ? "failure.png" : null,
          events: "events.jsonl",
        },
      },
      null,
      2,
    ) + "\n",
    "utf-8",
  );

  if (status === "failed") {
    process.exitCode = 1;
  }
}

void main();
