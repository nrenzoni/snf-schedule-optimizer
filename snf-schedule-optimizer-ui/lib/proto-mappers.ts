import {
  DaySchedule as ProtoDaySchedule,
  FinancialReport,
  Nurse as ProtoNurse,
  OptimizationRun,
  OptimizationRunStage,
  OptimizationRunStatus,
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
  shiftName: p.shiftName as UIShift["shiftName"],
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
): UIValidationLevel => {
  switch (level) {
    case ValidationLevel.VALIDATION_OK:
      return "ok";
    case ValidationLevel.VALIDATION_WARNING:
      return "warning";
    case ValidationLevel.VALIDATION_CRITICAL:
      return "critical";
    case ValidationLevel.VALIDATION_STALE:
      return "stale";
    case ValidationLevel.VALIDATION_LEVEL_UNSPECIFIED:
    default:
      return "unspecified";
  }
};

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

export const protoRunStatusToUI = (status: OptimizationRunStatus): UIOptimizationRun["status"] => {
  switch (status) {
    case OptimizationRunStatus.QUEUED:
      return "queued";
    case OptimizationRunStatus.RUNNING:
      return "running";
    case OptimizationRunStatus.COMPLETED:
      return "completed";
    case OptimizationRunStatus.FAILED:
      return "failed";
    case OptimizationRunStatus.UNSPECIFIED:
    default:
      return "unspecified";
  }
};

export const protoRunStageToUI = (stage: OptimizationRunStage): UIOptimizationRun["stage"] => {
  switch (stage) {
    case OptimizationRunStage.QUEUED:
      return "queued";
    case OptimizationRunStage.SNAPSHOTTING:
      return "snapshotting";
    case OptimizationRunStage.INDEXING:
      return "indexing";
    case OptimizationRunStage.BUILDING_MODEL:
      return "building_model";
    case OptimizationRunStage.SOLVING:
      return "solving";
    case OptimizationRunStage.ANALYZING:
      return "analyzing";
    case OptimizationRunStage.PUBLISHING:
      return "publishing";
    case OptimizationRunStage.COMPLETED:
      return "completed";
    case OptimizationRunStage.FAILED:
      return "failed";
    default:
      return "queued";
  }
};

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
  };
};
