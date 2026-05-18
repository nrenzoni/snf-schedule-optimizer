import {
  RunHistoryEntry,
  ScheduleMap,
  UIDaySchedule,
  UIOptimizationRunStage,
} from "@/types/scheduling";

export interface TreeNode {
  id: string;
  label: string;
  value?: string | number;
  children?: TreeNode[];
  defaultExpanded?: boolean;
}

const STAGE_LABELS: Record<UIOptimizationRunStage, string> = {
  unspecified: "Initializing",
  queued: "Queued",
  snapshotting: "Snapshotting",
  indexing: "Indexing",
  building_model: "Building Model",
  solving: "Solving",
  analyzing: "Analyzing",
  publishing: "Publishing",
  completed: "Completed",
  failed: "Failed",
};

function formatCurrency(value: number): string {
  return `$${Math.round(value).toLocaleString()}`;
}

function computeCoverageFromSchedule(schedule: Record<string, UIDaySchedule> | ScheduleMap): {
  covered: number;
  uncovered: number;
  total: number;
  uncoveredShifts: { date: string; shift: string; unit: string }[];
} {
  let covered = 0;
  let uncovered = 0;
  const uncoveredShifts: { date: string; shift: string; unit: string }[] = [];
  let total = 0;

  const days = schedule instanceof Map
    ? Array.from(schedule.values())
    : Object.values(schedule);

  for (const day of days) {
    for (const shift of day.shifts) {
      total++;
      if (shift.nurses.length > 0) {
        covered++;
      } else {
        uncovered++;
        uncoveredShifts.push({
          date: day.date,
          shift: shift.shiftName,
          unit: shift.unitName,
        });
      }
    }
  }

  return { covered, uncovered, total, uncoveredShifts };
}

function computeHPRDCompliance(schedule: Record<string, UIDaySchedule> | ScheduleMap): TreeNode[] {
  const byUnitShift: Map<string, { total: number; met: number; shifts: { date: string; shiftName: string; targetHprd: number; actualHprd: number }[] }> = new Map();

  const days = schedule instanceof Map
    ? Array.from(schedule.values())
    : Object.values(schedule);

  for (const day of days) {
    for (const shift of day.shifts) {
      const key = `${shift.unitName} ${shift.shiftName}`;
      let entry = byUnitShift.get(key);
      if (!entry) {
        entry = { total: 0, met: 0, shifts: [] };
        byUnitShift.set(key, entry);
      }
      entry.total++;
      if (shift.isHPRDMet) entry.met++;
      entry.shifts.push({
        date: day.date,
        shiftName: shift.shiftName,
        targetHprd: shift.requiredHPRD,
        actualHprd: shift.requiredHPRD > 0 ? shift.actualHours / shift.patientCount : 0,
      });
    }
  }

  const nodes: TreeNode[] = [];
  for (const [key, entry] of byUnitShift.entries()) {
    const [unit, shiftName] = key.split(" ");
    nodes.push({
      id: `hprd-${key}`,
      label: `${unit} ${shiftName}`,
      value: `${entry.met}/${entry.total} met`,
      defaultExpanded: false,
    });
  }
  return nodes;
}

function computePerDayCoverage(schedule: Record<string, UIDaySchedule> | ScheduleMap): TreeNode[] {
  const nodes: TreeNode[] = [];
  const days = schedule instanceof Map
    ? Array.from(schedule.entries())
    : Object.entries(schedule);

  for (const [date, day] of days) {
    const total = day.shifts.length;
    const covered = day.shifts.filter((s) => s.nurses.length > 0).length;
    nodes.push({
      id: `day-${date}`,
      label: date,
      value: `${covered}/${total} covered`,
      defaultExpanded: false,
      children: day.shifts.map((s) => ({
        id: `shift-${date}-${s.shiftId}`,
        label: s.shiftName,
        value: s.nurses.length > 0 ? `${s.nurses.length} nurses` : "UNCOVERED",
      })),
    });
  }
  return nodes;
}

function computeNurseChanges(
  preSchedule: Record<string, UIDaySchedule>,
  postSchedule: Record<string, UIDaySchedule>,
): TreeNode[] {
  const nodes: TreeNode[] = [];
  const preAssignments = new Map<string, string[]>();
  const postAssignments = new Map<string, string[]>();

  for (const day of Object.values(preSchedule)) {
    for (const shift of day.shifts) {
      for (const nurse of shift.nurses) {
        const existing = preAssignments.get(nurse.id) || [];
        existing.push(`${day.date} ${shift.shiftName} @ ${shift.unitName}`);
        preAssignments.set(nurse.id, existing);
      }
    }
  }

  for (const day of Object.values(postSchedule)) {
    for (const shift of day.shifts) {
      for (const nurse of shift.nurses) {
        const existing = postAssignments.get(nurse.id) || [];
        existing.push(`${day.date} ${shift.shiftName} @ ${shift.unitName}`);
        postAssignments.set(nurse.id, existing);
      }
    }
  }

  for (const [nurseId, preShifts] of preAssignments) {
    const postShifts = postAssignments.get(nurseId) || [];
    const preSet = new Set(preShifts);
    const postSet = new Set(postShifts);
    const added = postShifts.filter((s) => !preSet.has(s));
    const removed = preShifts.filter((s) => !postSet.has(s));

    if (added.length > 0 || removed.length > 0) {
      nodes.push({
        id: `nurse-${nurseId}`,
        label: `Nurse ${nurseId}`,
        value: `${removed.length} removed, ${added.length} added`,
        defaultExpanded: false,
        children: [
          ...removed.map((s) => ({
            id: `rem-${nurseId}-${s}`,
            label: `- ${s}`,
          })),
          ...added.map((s) => ({
            id: `add-${nurseId}-${s}`,
            label: `+ ${s}`,
          })),
        ],
      });
    }
  }

  return nodes;
}

export function buildTreeData(
  entry: RunHistoryEntry,
  postSchedule: Record<string, UIDaySchedule>,
): TreeNode[] {
  const { run } = entry;
  const preSched = entry.preSchedule;
  const postSched = entry.postSchedule ?? postSchedule;

  const coverage = computeCoverageFromSchedule(postSched);
  const isCompleted = run.status === "completed";

  const runOverview: TreeNode[] = [
    {
      id: "status",
      label: "Status",
      value: isCompleted ? "Completed" : run.status,
    },
    ...(run.runId ? [{
      id: "runId",
      label: "Run ID",
      value: run.runId.slice(0, 8),
    }] : []),
    ...(run.baseScheduleVersion ? [{
      id: "scheduleVersion",
      label: "Schedule Version",
      value: `${run.baseScheduleVersion}${run.resultScheduleVersion ? ` \u2192 ${run.resultScheduleVersion}` : ""}`,
    }] : []),
    ...(run.startedAt && run.completedAt ? [{
      id: "duration",
      label: "Duration",
      value: `${Math.round(
        (new Date(run.completedAt).getTime() - new Date(run.startedAt).getTime()),
      )} ms`,
    }] : []),
    ...(run.completedAt ? [{
      id: "completedAt",
      label: "Completed At",
      value: new Date(run.completedAt).toLocaleString(),
    }] : []),
    ...(run.errorDetails ? [{
      id: "errorDetails",
      label: "Error",
      value: run.errorDetails,
    }] : []),
  ];

  const coverageNodes: TreeNode[] = [
    {
      id: "coveredShifts",
      label: "Covered Shifts",
      value: coverage.covered,
    },
    {
      id: "uncoveredShifts",
      label: "Uncovered Shifts",
      value: coverage.uncovered,
      children: coverage.uncoveredShifts.length > 0
        ? coverage.uncoveredShifts.map((u) => ({
            id: `uncov-${u.date}-${u.shift}`,
            label: `${u.date} / ${u.shift}`,
            value: u.unit,
          }))
        : undefined,
    },
    {
      id: "totalAssignments",
      label: "Total Assignments",
      value: coverage.total,
    },
    {
      id: "hprdCompliance",
      label: "HPRD Compliance",
      value: run.summary
        ? `${run.summary.coveredShifts}/${run.summary.totalAssignments} met`
        : `${coverage.covered}/${coverage.total} met`,
      children: computeHPRDCompliance(postSched),
    },
  ];

  const staffingNodes: TreeNode[] = [
    {
      id: "assignmentsChanged",
      label: "Assignments Changed",
      value: run.summary?.assignmentsChanged ?? "N/A",
    },
  ];

  if (preSched && Object.keys(preSched).length > 0 && postSched && Object.keys(postSched).length > 0) {
    const nurseChanges = computeNurseChanges(preSched, postSched);
    if (nurseChanges.length > 0) {
      staffingNodes.push({
        id: "nurseChanges",
        label: "Per-Nurse Changes",
        value: `${nurseChanges.length} nurses affected`,
        children: nurseChanges,
      });
    }
  }

  const financialNodes: TreeNode[] = run.financials ? [
    {
      id: "totalCost",
      label: "Total Enterprise Cost",
      value: formatCurrency(run.financials.totalEnterpriseCost),
      children: [
        { id: "regularPay", label: "Regular Pay", value: formatCurrency(run.financials.regularPayCost) },
        { id: "overtimeCost", label: "Overtime Cost", value: formatCurrency(run.financials.totalOvertimeCost) },
        { id: "incentiveCost", label: "Incentive Cost", value: formatCurrency(run.financials.totalIncentiveCost) },
      ],
    },
  ] : [];

  const solverNodes: TreeNode[] = run.stats ? [
    { id: "objective", label: "Objective Value", value: run.stats.objectiveValue.toFixed(2) },
    { id: "executionTime", label: "Execution Time", value: `${Math.round(run.stats.executionTimeMs)} ms` },
    { id: "totalVariables", label: "Variables", value: run.stats.totalVariables },
    { id: "totalConstraints", label: "Constraints", value: run.stats.totalConstraints },
  ] : [];

  const stageTimingNodes: TreeNode[] = run.stageTimings.length > 0
    ? run.stageTimings.map((st) => ({
        id: `stage-${st.stage}`,
        label: STAGE_LABELS[st.stage] || st.stage,
        value: `${st.durationMs} ms`,
      }))
    : [
        ...(run.stage
          ? [{ id: "currentStage", label: "Current Stage", value: STAGE_LABELS[run.stage] || run.stage }]
          : []),
        ...(run.completedAt && run.startedAt
          ? [{
              id: "totalDuration",
              label: "Total Duration",
              value: `${new Date(run.completedAt).getTime() - new Date(run.startedAt).getTime()} ms`,
            }]
          : []),
      ];

  const settingsNodes: TreeNode[] = run.summary?.appliedSettings ? [
    { id: "useMLForecast", label: "ML Forecast", value: run.summary.appliedSettings.useMLForecast ? "On" : "Off" },
    { id: "bufferThreshold", label: "Callout Buffer", value: `${run.summary.appliedSettings.bufferThreshold}%` },
    { id: "minRestPeriod", label: "Min Rest Period", value: `${run.summary.appliedSettings.minRestPeriod} hrs` },
    { id: "maxShiftLength", label: "Max Shift Length", value: `${run.summary.appliedSettings.maxShiftLength} hrs` },
    { id: "premiumWeekend", label: "Weekend Premium", value: run.summary.appliedSettings.premiumWeekend ? "On" : "Off" },
    { id: "premiumHoliday", label: "Holiday Premium", value: run.summary.appliedSettings.premiumHoliday ? "On" : "Off" },
    { id: "otPenalty", label: "OT Avoidance Penalty", value: run.summary.appliedSettings.overtimeAvoidancePenalty },
    { id: "teamConsistency", label: "Team Consistency", value: run.summary.appliedSettings.teamConsistencyPenalty },
    { id: "highRiskShift", label: "High Risk Shift", value: run.summary.appliedSettings.highRiskShiftPenalty },
    { id: "customPreference", label: "Custom Preference", value: run.summary.appliedSettings.customPreferencePenalty },
  ] : [];

  const topLevel: TreeNode[] = [
    {
      id: "runOverview",
      label: "Run Overview",
      value: isCompleted ? "Completed" : run.status,
      children: runOverview,
      defaultExpanded: true,
    },
    {
      id: "coverageHPRD",
      label: "Coverage & HPRD",
      value: `${coverage.covered}/${coverage.total} covered (${coverage.total > 0 ? Math.round((coverage.covered / coverage.total) * 100) : 0}%)`,
      children: [
        ...coverageNodes,
        {
          id: "perDayCoverage",
          label: "Per-Day Coverage",
          children: computePerDayCoverage(postSched),
        },
      ],
      defaultExpanded: true,
    },
    {
      id: "staffing",
      label: "Staffing Changes",
      value: run.summary ? `${run.summary.assignmentsChanged} changed` : "N/A",
      children: staffingNodes,
    },
    ...(financialNodes.length > 0 ? [{
      id: "financial",
      label: "Financial Impact",
      value: run.financials ? formatCurrency(run.financials.totalEnterpriseCost) : "N/A",
      children: financialNodes,
    }] : []),
    ...(solverNodes.length > 0 ? [{
      id: "solver",
      label: "Solver Metrics",
      value: run.stats ? `${Math.round(run.stats.executionTimeMs)} ms` : "N/A",
      children: solverNodes,
    }] : []),
    {
      id: "stageTimeline",
      label: "Stage Timeline",
      value: run.stageTimings.length > 0
        ? `${run.stageTimings[run.stageTimings.length - 1]?.durationMs ?? "?"} ms last stage`
        : "N/A",
      children: stageTimingNodes,
    },
    ...(settingsNodes.length > 0 ? [{
      id: "appliedSettings",
      label: "Applied Settings",
      value: `${settingsNodes.length} parameters`,
      children: settingsNodes,
    }] : []),
  ];

  return topLevel;
}
