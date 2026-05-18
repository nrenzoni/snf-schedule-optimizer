import test from "node:test";
import assert from "node:assert/strict";
import { buildTreeData } from "@/lib/optimization-tree-data";
import type { RunHistoryEntry, UIDaySchedule, UIOptimizationRun } from "@/types/scheduling";

function makeMockRun(overrides: Partial<UIOptimizationRun> = {}): UIOptimizationRun {
  return {
    runId: "run-001",
    scheduleId: "sched-01",
    baseScheduleVersion: 5,
    resultScheduleVersion: 6,
    status: "completed",
    stage: "completed",
    progressPercent: 100,
    statusMessage: "Optimization complete",
    startedAt: "2026-05-17T10:00:00Z",
    completedAt: "2026-05-17T10:02:30Z",
    errorDetails: null,
    financials: {
      totalEnterpriseCost: 48000,
      totalIncentiveCost: 1800,
      totalOvertimeCost: 3200,
      regularPayCost: 43000,
    },
    stats: {
      executionTimeMs: 2340,
      objectiveValue: -12540.5,
      totalVariables: 15200,
      totalConstraints: 8450,
    },
    summary: {
      assignmentsChanged: 15,
      totalAssignments: 120,
      coveredShifts: 42,
      uncoveredShifts: 3,
      completedAt: "2026-05-17T10:02:30Z",
      appliedSettings: {
        useMLForecast: false,
        useCalloutBuffer: true,
        bufferThreshold: 10,
        minRestPeriod: 10,
        maxShiftLength: 12,
        premiumWeekend: true,
        premiumHoliday: false,
        overtimeAvoidancePenalty: 1000,
        teamConsistencyPenalty: 300,
        highRiskShiftPenalty: 2000,
        customPreferencePenalty: 1500,
      },
    },
    stageTimings: [],
    ...overrides,
  };
}

function makeMockDaySchedule(date: string, shifts: {
  shiftId: string;
  shiftName: "Morning" | "Afternoon" | "Night";
  unitName: string;
  unitId: string;
  patientCount: number;
  requiredHPRD: number;
  nurseCount: number;
  isHPRDMet: boolean;
}[]): UIDaySchedule {
  return {
    date,
    shifts: shifts.map((s) => ({
      shiftId: s.shiftId,
      shiftName: s.shiftName,
      unitId: s.unitId,
      unitName: s.unitName,
      patientCount: s.patientCount,
      requiredHPRD: s.requiredHPRD,
      requiredHours: s.patientCount * s.requiredHPRD,
      actualHours: s.nurseCount * 8,
      isHPRDMet: s.isHPRDMet,
      nurses: Array.from({ length: s.nurseCount }, (_, i) => ({
        id: `nurse-${s.shiftId}-${i}`,
        name: `Nurse ${i + 1}`,
        role: "RN",
        shiftHours: 8,
        schedulingRationale: "test",
        isAgency: false,
      })),
    })),
  };
}

function makeMockEntry(overrides: {
  preSchedule?: Record<string, UIDaySchedule>;
  postSchedule?: Record<string, UIDaySchedule>;
  runOverrides?: Partial<UIOptimizationRun>;
} = {}): RunHistoryEntry {
  const run = makeMockRun(overrides.runOverrides);
  return {
    run,
    preSchedule: overrides.preSchedule ?? {},
    postSchedule: overrides.postSchedule ?? {},
    stagedPatches: [],
    completedAt: run.completedAt ?? new Date().toISOString(),
  };
}

test("buildTreeData returns all expected top-level nodes for a completed run", () => {
  const entry = makeMockEntry({
    postSchedule: {
      "2026-05-17": makeMockDaySchedule("2026-05-17", [
        { shiftId: "s1", shiftName: "Morning", unitName: "Unit-A", unitId: "u1", patientCount: 10, requiredHPRD: 3.0, nurseCount: 4, isHPRDMet: true },
        { shiftId: "s2", shiftName: "Afternoon", unitName: "Unit-A", unitId: "u1", patientCount: 10, requiredHPRD: 3.0, nurseCount: 3, isHPRDMet: false },
      ]),
    },
  });

  const tree = buildTreeData(entry, entry.postSchedule!);

  assert.ok(tree.length > 0, "Tree should have top-level nodes");
  const ids = tree.map((n) => n.id);
  assert.ok(ids.includes("runOverview"));
  assert.ok(ids.includes("coverageHPRD"));
  assert.ok(ids.includes("staffing"));
  assert.ok(ids.includes("financial"));
  assert.ok(ids.includes("solver"));
  assert.ok(ids.includes("stageTimeline"));
  assert.ok(ids.includes("appliedSettings"));
});

test("buildTreeData run overview shows status and is expanded by default", () => {
  const entry = makeMockEntry({
    postSchedule: { "2026-05-17": makeMockDaySchedule("2026-05-17", []) },
    runOverrides: { status: "completed" },
  });

  const tree = buildTreeData(entry, entry.postSchedule!);
  const overviewNode = tree.find((n) => n.id === "runOverview");

  assert.ok(overviewNode, "Run overview node should exist");
  assert.equal(overviewNode!.value, "Completed");
  assert.ok(overviewNode!.children, "Run overview should have children");
  assert.ok(overviewNode!.defaultExpanded, "Run overview should be expanded by default");

  const statusChild = overviewNode!.children!.find((c) => c.id === "status");
  assert.ok(statusChild, "Status child should exist");
  assert.equal(statusChild!.value, "Completed");
});

test("buildTreeData computes coverage percentages from post-schedule", () => {
  const postSchedule: Record<string, UIDaySchedule> = {
    "2026-05-17": makeMockDaySchedule("2026-05-17", [
      { shiftId: "s1", shiftName: "Morning", unitName: "Unit-A", unitId: "u1", patientCount: 10, requiredHPRD: 3.0, nurseCount: 4, isHPRDMet: true },
      { shiftId: "s2", shiftName: "Afternoon", unitName: "Unit-A", unitId: "u1", patientCount: 10, requiredHPRD: 3.0, nurseCount: 0, isHPRDMet: false },
      { shiftId: "s3", shiftName: "Night", unitName: "Unit-A", unitId: "u1", patientCount: 10, requiredHPRD: 3.0, nurseCount: 2, isHPRDMet: false },
    ]),
  };

  const entry = makeMockEntry({ postSchedule });
  const tree = buildTreeData(entry, postSchedule);

  const coverageNode = tree.find((n) => n.id === "coverageHPRD");
  assert.ok(coverageNode, "Coverage node should exist");
  assert.equal(coverageNode!.value, "2/3 covered (67%)");

  const coveredChild = coverageNode!.children!.find((c) => c.id === "coveredShifts");
  assert.ok(coveredChild);
  assert.equal(coveredChild!.value, 2);

  const uncoveredChild = coverageNode!.children!.find((c) => c.id === "uncoveredShifts");
  assert.ok(uncoveredChild);
  assert.equal(uncoveredChild!.value, 1);
});

test("buildTreeData uncovered shifts lists specific shifts", () => {
  const postSchedule: Record<string, UIDaySchedule> = {
    "2026-05-17": makeMockDaySchedule("2026-05-17", [
      { shiftId: "s1", shiftName: "Morning", unitName: "Unit-A", unitId: "u1", patientCount: 10, requiredHPRD: 3.0, nurseCount: 0, isHPRDMet: false },
    ]),
  };

  const entry = makeMockEntry({ postSchedule });
  const tree = buildTreeData(entry, postSchedule);

  const coverageNode = tree.find((n) => n.id === "coverageHPRD");
  const uncoveredChild = coverageNode!.children!.find((c) => c.id === "uncoveredShifts");
  assert.ok(uncoveredChild);
  assert.ok(uncoveredChild!.children);
  assert.ok(uncoveredChild!.children!.length > 0);
  assert.ok(uncoveredChild!.children![0].id.includes("2026-05-17"));
});

test("buildTreeData shows financial data from run", () => {
  const entry = makeMockEntry({
    postSchedule: { "2026-05-17": makeMockDaySchedule("2026-05-17", []) },
  });

  const tree = buildTreeData(entry, entry.postSchedule!);
  const financialNode = tree.find((n) => n.id === "financial");

  assert.ok(financialNode, "Financial node should exist");
  assert.equal(financialNode!.value, "$48,000");
  assert.ok(financialNode!.children, "Financial node should have children");

  const totalCostChild = financialNode!.children!.find((c) => c.id === "totalCost");
  assert.ok(totalCostChild, "Total cost child should exist");
});

test("buildTreeData shows solver metrics from run", () => {
  const entry = makeMockEntry({
    postSchedule: { "2026-05-17": makeMockDaySchedule("2026-05-17", []) },
  });

  const tree = buildTreeData(entry, entry.postSchedule!);
  const solverNode = tree.find((n) => n.id === "solver");

  assert.ok(solverNode, "Solver node should exist");
  assert.equal(solverNode!.value, "2340 ms");

  const objChild = solverNode!.children!.find((c) => c.id === "objective");
  assert.ok(objChild);
  assert.equal(objChild!.value, "-12540.50");
});

test("buildTreeData shows applied settings from run summary", () => {
  const entry = makeMockEntry({
    postSchedule: { "2026-05-17": makeMockDaySchedule("2026-05-17", []) },
  });

  const tree = buildTreeData(entry, entry.postSchedule!);
  const settingsNode = tree.find((n) => n.id === "appliedSettings");

  assert.ok(settingsNode, "Settings node should exist");
  assert.equal(settingsNode!.value, "10 parameters");
  assert.ok(settingsNode!.children, "Settings should have children");
  assert.ok(settingsNode!.children!.length >= 8);
});

test("buildTreeData handles failed run with error details", () => {
  const entry = makeMockEntry({
    postSchedule: {},
    runOverrides: {
      status: "failed",
      stage: "failed",
      errorDetails: "Solver timeout after 60s",
      financials: null,
      stats: null,
      summary: null,
      completedAt: null,
    },
  });

  const tree = buildTreeData(entry, {});
  const overviewNode = tree.find((n) => n.id === "runOverview");
  assert.ok(overviewNode);

  const statusChild = overviewNode!.children!.find((c) => c.id === "status");
  assert.ok(statusChild);
  assert.equal(statusChild!.value, "failed");

  const errorChild = overviewNode!.children!.find((c) => c.id === "errorDetails");
  assert.ok(errorChild);
  assert.equal(errorChild!.value, "Solver timeout after 60s");
});

test("buildTreeData includes stage timings when present on run", () => {
  const entry = makeMockEntry({
    postSchedule: {},
    runOverrides: {
      stageTimings: [
        { stage: "snapshotting", durationMs: 150 },
        { stage: "indexing", durationMs: 200 },
        { stage: "building_model", durationMs: 400 },
        { stage: "solving", durationMs: 1500 },
      ],
    },
  });

  const tree = buildTreeData(entry, {});
  const stageNode = tree.find((n) => n.id === "stageTimeline");
  assert.ok(stageNode, "Stage timeline node should exist");
  assert.equal(stageNode!.value, "1500 ms last stage");
  assert.ok(stageNode!.children);
  assert.ok(stageNode!.children!.length >= 4);
});

test("buildTreeData handles empty schedule gracefully", () => {
  const entry = makeMockEntry({
    postSchedule: {},
  });

  const tree = buildTreeData(entry, {});

  const coverageNode = tree.find((n) => n.id === "coverageHPRD");
  assert.ok(coverageNode);
  assert.equal(coverageNode!.value, "0/0 covered (0%)");
});

test("buildTreeData per-day coverage shows correct values", () => {
  const postSchedule: Record<string, UIDaySchedule> = {
    "2026-05-17": makeMockDaySchedule("2026-05-17", [
      { shiftId: "s1", shiftName: "Morning", unitName: "Unit-A", unitId: "u1", patientCount: 10, requiredHPRD: 3.0, nurseCount: 4, isHPRDMet: true },
      { shiftId: "s2", shiftName: "Afternoon", unitName: "Unit-A", unitId: "u1", patientCount: 10, requiredHPRD: 3.0, nurseCount: 3, isHPRDMet: true },
    ]),
    "2026-05-18": makeMockDaySchedule("2026-05-18", [
      { shiftId: "s3", shiftName: "Morning", unitName: "Unit-A", unitId: "u1", patientCount: 10, requiredHPRD: 3.0, nurseCount: 0, isHPRDMet: false },
    ]),
  };

  const entry = makeMockEntry({ postSchedule });
  const tree = buildTreeData(entry, postSchedule);

  const coverageNode = tree.find((n) => n.id === "coverageHPRD");
  const perDayNode = coverageNode!.children!.find((c) => c.id === "perDayCoverage");
  assert.ok(perDayNode);
  assert.ok(perDayNode!.children);

  const day17 = perDayNode!.children!.find((c) => c.id === "day-2026-05-17");
  assert.ok(day17);
  assert.equal(day17!.value, "2/2 covered");

  const day18 = perDayNode!.children!.find((c) => c.id === "day-2026-05-18");
  assert.ok(day18);
  assert.equal(day18!.value, "0/1 covered");
});

test("buildTreeData financial node missing when run has null financials", () => {
  const entry = makeMockEntry({
    postSchedule: {},
    runOverrides: { financials: null },
  });

  const tree = buildTreeData(entry, {});
  const financialNode = tree.find((n) => n.id === "financial");
  assert.equal(financialNode, undefined, "Financial node should be omitted when null");
});

test("buildTreeData solver node missing when run has null stats", () => {
  const entry = makeMockEntry({
    postSchedule: {},
    runOverrides: { stats: null },
  });

  const tree = buildTreeData(entry, {});
  const solverNode = tree.find((n) => n.id === "solver");
  assert.equal(solverNode, undefined, "Solver node should be omitted when null");
});
