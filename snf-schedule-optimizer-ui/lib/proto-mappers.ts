import { create } from "@bufbuild/protobuf";
import { match } from "ts-pattern";
import {
  DaySchedule as ProtoDaySchedule,
  FinancialReport,
  Nurse as ProtoNurse,
  OptimizationRun,
  OptimizationRunStage,
  OptimizationRunStatus,
  OptimizationSettingsSchema,
  OptimizationStats,
  OptimizationSummary,
  PatchConflict,
  StagedSchedulePatch,
  Shift as ProtoShift,
  ValidationLevel,
} from "@/gen/scheduling/v1/scheduling_pb";
import {
  UIDaySchedule,
  UIFinancials,
  UIOptimizationRun,
  UIOptimizationStats,
  UIOptimizationSummary,
  UIPatchConflict,
  UISchedulerSettings,
  UIStagedPatch,
  UIValidationLevel,
  UINurse,
  UIShift,
} from "@/types/scheduling";

export const protoNurseToUI = (nurse: ProtoNurse): UINurse => ({
  id: nurse.id,
  name: nurse.name,
  role: nurse.role,
  shiftHours: nurse.shiftHours,
  schedulingRationale: nurse.schedulingRationale,
  isAgency: nurse.isAgency,
});

export const protoShiftToUI = (p: ProtoShift): UIShift => ({
  shiftId: p.shiftId,
  shiftName: match(p.shiftName)
    .with("Morning", () => "Morning" as const)
    .with("Afternoon", () => "Afternoon" as const)
    .with("Night", () => "Night" as const)
    .otherwise(() => "Morning" as const),
  unitId: p.unitId || "unit-unknown",
  unitName: p.unitName || "Unassigned Unit",
  patientCount: p.patientCensus,
  requiredHPRD: p.targetHrpd ?? 0,
  requiredHours: (p.patientCensus ?? 0) * (p.targetHrpd ?? 0),
  actualHours: (p.patientCensus ?? 0) * (p.actualHrpd ?? 0),
  isHPRDMet: p.isHrpdMet ?? false,
  nurses: (p.nurses || []).map(protoNurseToUI),
});

export const protoDayToUI = (d: ProtoDaySchedule): UIDaySchedule => ({
  date: d.date,
  shifts: (d.shifts || []).map(protoShiftToUI),
});

export const protoSummaryToUI = (summary?: OptimizationSummary): UIOptimizationSummary | null => {
  if (!summary) {
    return null;
  }
  return {
    assignmentsChanged: summary.assignmentsChanged,
    totalAssignments: summary.totalAssignments,
    coveredShifts: summary.coveredShifts,
    uncoveredShifts: summary.uncoveredShifts,
    completedAt: summary.completedAt,
    appliedSettings: {
      useMLForecast: summary.appliedSettings?.useMlForecast ?? false,
      useCalloutBuffer: summary.appliedSettings?.useCalloutBuffer ?? false,
      bufferThreshold: summary.appliedSettings?.bufferThreshold ?? 0,
      minRestPeriod: summary.appliedSettings?.minRestPeriod ?? 0,
      maxShiftLength: summary.appliedSettings?.maxShiftLength ?? 0,
      premiumWeekend: summary.appliedSettings?.premiumWeekend ?? false,
      premiumHoliday: summary.appliedSettings?.premiumHoliday ?? false,
      overtimeAvoidancePenalty:
        summary.appliedSettings?.overtimeAvoidancePenalty ?? 0,
      teamConsistencyPenalty:
        summary.appliedSettings?.teamConsistencyPenalty ?? 0,
      highRiskShiftPenalty: summary.appliedSettings?.highRiskShiftPenalty ?? 0,
      customPreferencePenalty:
        summary.appliedSettings?.customPreferencePenalty ?? 0,
    },
  };
};

export const protoFinancialsToUI = (financials?: FinancialReport): UIFinancials | null => {
  if (!financials) {
    return null;
  }
  return {
    totalEnterpriseCost: financials.totalEnterpriseCost,
    totalIncentiveCost: financials.totalIncentiveCost,
    totalOvertimeCost: financials.totalOvertimeCost,
    regularPayCost: financials.regularPayCost,
  };
};

export const protoStatsToUI = (stats?: OptimizationStats): UIOptimizationStats | null => {
  if (!stats) {
    return null;
  }
  return {
    executionTimeMs: stats.executionTimeMs,
    objectiveValue: stats.objectiveValue,
    totalVariables: stats.totalVariables,
    totalConstraints: stats.totalConstraints,
  };
};

export const protoValidationLevelToUI = (
  level: ValidationLevel | undefined,
): UIValidationLevel =>
  match(level ?? ValidationLevel.VALIDATION_LEVEL_UNSPECIFIED)
    .with(ValidationLevel.VALIDATION_OK, () => "ok" as const)
    .with(ValidationLevel.VALIDATION_WARNING, () => "warning" as const)
    .with(ValidationLevel.VALIDATION_CRITICAL, () => "critical" as const)
    .with(ValidationLevel.VALIDATION_STALE, () => "stale" as const)
    .otherwise(() => "unspecified" as const);

export const protoPatchConflictToUI = (conflict: PatchConflict): UIPatchConflict => ({
  patchId: conflict.patchId,
  employeeId: conflict.employeeId,
  employeeName: conflict.employeeName || null,
  fromShiftId: conflict.fromShiftId || null,
  toShiftId: conflict.toShiftId || null,
  reason: conflict.reason,
  latestShiftId: conflict.latestShiftId || null,
});

export const protoStagedPatchToUI = (patch: StagedSchedulePatch): UIStagedPatch => ({
  patchId: patch.patchId,
  employeeId: patch.employeeId,
  employeeName: patch.employeeName || null,
  fromShiftId: patch.fromShiftId || null,
  toShiftId: patch.toShiftId || null,
  pinned: patch.pinned,
  warnings: patch.warnings,
  validationLevel: protoValidationLevelToUI(patch.validationLevel),
  causesOvertime: patch.causesOvertime,
  totalCost: patch.totalCost,
  createdAt: patch.createdAt || null,
});

export const protoRunStatusToUI = (status: OptimizationRunStatus): UIOptimizationRun["status"] =>
  match(status)
    .with(OptimizationRunStatus.QUEUED, () => "queued" as const)
    .with(OptimizationRunStatus.RUNNING, () => "running" as const)
    .with(OptimizationRunStatus.COMPLETED, () => "completed" as const)
    .with(OptimizationRunStatus.FAILED, () => "failed" as const)
    .otherwise(() => "unspecified" as const);

export const protoRunStageToUI = (stage: OptimizationRunStage): UIOptimizationRun["stage"] =>
  match(stage)
    .with(OptimizationRunStage.QUEUED, () => "queued" as const)
    .with(OptimizationRunStage.SNAPSHOTTING, () => "snapshotting" as const)
    .with(OptimizationRunStage.INDEXING, () => "indexing" as const)
    .with(OptimizationRunStage.BUILDING_MODEL, () => "building_model" as const)
    .with(OptimizationRunStage.SOLVING, () => "solving" as const)
    .with(OptimizationRunStage.ANALYZING, () => "analyzing" as const)
    .with(OptimizationRunStage.PUBLISHING, () => "publishing" as const)
    .with(OptimizationRunStage.COMPLETED, () => "completed" as const)
    .with(OptimizationRunStage.FAILED, () => "failed" as const)
    .otherwise(() => "unspecified" as const);

export const protoOptimizationRunToUI = (
  run?: OptimizationRun,
): UIOptimizationRun | null => {
  if (!run?.runId) {
    return null;
  }

  return {
    runId: run.runId,
    scheduleId: run.scheduleId,
    baseScheduleVersion: run.baseScheduleVersion,
    resultScheduleVersion: run.resultScheduleVersion || null,
    status: protoRunStatusToUI(run.status),
    stage: protoRunStageToUI(run.stage),
    progressPercent: run.progressPercent,
    statusMessage: run.statusMessage,
    startedAt: run.startedAt || null,
    completedAt: run.completedAt || null,
    errorDetails: run.errorDetails || null,
    financials: protoFinancialsToUI(run.financials),
    stats: protoStatsToUI(run.stats),
    summary: protoSummaryToUI(run.summary),
    stageTimings: [],
  };
};

export const uiSettingsToProto = (settings: UISchedulerSettings) =>
  create(OptimizationSettingsSchema, {
    useMlForecast: settings.useMLForecast,
    useCalloutBuffer: settings.useCalloutBuffer,
    bufferThreshold: settings.bufferThreshold,
    minRestPeriod: settings.minRestPeriod,
    maxShiftLength: settings.maxShiftLength,
    premiumWeekend: settings.premiumWeekend,
    premiumHoliday: settings.premiumHoliday,
    overtimeAvoidancePenalty: settings.overtimeAvoidancePenalty,
    teamConsistencyPenalty: settings.teamConsistencyPenalty,
    highRiskShiftPenalty: settings.highRiskShiftPenalty,
    customPreferencePenalty: settings.customPreferencePenalty,
  });
