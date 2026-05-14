import { useQuery } from "@tanstack/react-query";
import { formatDateYYYMMDD } from "@/utils/scheduling-logic";
import { useSchedulingStore } from "@/store/schedulingStore";
import {
  ScheduleMap,
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
import { useShallow } from "zustand/react/shallow";
import {
  DaySchedule as ProtoDaySchedule,
  FinancialReport,
  Nurse as ProtoNurse,
  OptimizationRun,
  OptimizationRunStage,
  OptimizationRunStatus,
  OptimizationStats,
  OptimizationSummary,
  OrgFacility,
  PatchConflict,
  StagedSchedulePatch,
  Shift as ProtoShift,
  ValidationLevel,
} from "@/gen/scheduling/v1/scheduling_pb";
import { configuredBaseUrl, schedulingClient } from "@/api/scheduling-client";
import { useEffect } from "react";

type ScheduleQueryErrorCode =
  | "NO_FACILITIES"
  | "API_UNAVAILABLE"
  | "MISSING_API_BASE_URL"
  | "UNKNOWN";

export class ScheduleQueryError extends Error {
  constructor(
    message: string,
    public readonly code: ScheduleQueryErrorCode,
  ) {
    super(message);
    this.name = "ScheduleQueryError";
  }
}

const protoNurseToUI = (nurse: ProtoNurse): UINurse => ({
  id: nurse.id,
  name: nurse.name,
  role: nurse.role,
  shiftHours: nurse.shiftHours,
  schedulingRationale: nurse.schedulingRationale,
  isAgency: nurse.isAgency,
});

const protoShiftToUI = (p: ProtoShift): UIShift => ({
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

const protoSummaryToUI = (summary?: OptimizationSummary): UIOptimizationSummary | null => {
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

const protoValidationLevelToUI = (
  level: ValidationLevel | undefined,
): UIValidationLevel => {
  switch (level) {
    case ValidationLevel.VALIDATION_WARNING:
      return "warning";
    case ValidationLevel.VALIDATION_CRITICAL:
      return "critical";
    case ValidationLevel.VALIDATION_STALE:
      return "stale";
    case ValidationLevel.VALIDATION_OK:
    default:
      return "ok";
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

const protoRunStatusToUI = (status: OptimizationRunStatus): UIOptimizationRun["status"] => {
  switch (status) {
    case OptimizationRunStatus.QUEUED:
      return "queued";
    case OptimizationRunStatus.COMPLETED:
      return "completed";
    case OptimizationRunStatus.FAILED:
      return "failed";
    case OptimizationRunStatus.RUNNING:
    default:
      return "running";
  }
};

const protoRunStageToUI = (stage: OptimizationRunStage): UIOptimizationRun["stage"] => {
  switch (stage) {
    case OptimizationRunStage.QUEUED:
      return "queued";
    case OptimizationRunStage.REBASING:
      return "rebase";
    case OptimizationRunStage.SOLVING:
      return "solving";
    case OptimizationRunStage.ANALYZING:
      return "analyzing";
    case OptimizationRunStage.PERSISTING:
      return "persisting";
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
  if (!run) {
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

interface ScheduleQueryKey {
  startDate: string;
  endDate: string;
}

async function fetchScheduleData({
  startDate,
  endDate,
}: ScheduleQueryKey): Promise<{
  scheduleMap: ScheduleMap;
  selectedFacility: OrgFacility;
  scheduleId: string;
  scheduleVersion: number;
  latestOptimization: UIOptimizationSummary | null;
  optimizationStats: UIOptimizationStats | null;
  optimizationFinancials: UIFinancials | null;
  activeRun: UIOptimizationRun | null;
  updatedAt: string | null;
}> {
  if (!configuredBaseUrl) {
    throw new ScheduleQueryError(
      "The UI is missing NEXT_PUBLIC_API_BASE_URL. Configure an explicit backend base URL and reload the app.",
      "MISSING_API_BASE_URL",
    );
  }

  const facilities = await schedulingClient.getAllOrgFacilities({}).catch((error) => {
    throw new ScheduleQueryError(
      error instanceof Error ? error.message : "The scheduling API is unavailable.",
      "API_UNAVAILABLE",
    );
  });
  const selectedFacility = facilities.allOrgFacilities.at(0);

  if (!selectedFacility) {
    throw new ScheduleQueryError(
      "No facilities were returned by the scheduling API.",
      "NO_FACILITIES",
    );
  }

  const response = await schedulingClient.getMonthlySchedule({
    orgId: selectedFacility.orgId,
    facilityId: selectedFacility.facilityId,
    startDate,
    endDate,
  });

  const newSchedules = new Map<string, UIDaySchedule>();
  Object.entries(response.schedules).forEach(([dateStr, schedule]) => {
    newSchedules.set(dateStr, protoDayToUI(schedule as ProtoDaySchedule));
  });
  return {
    scheduleMap: newSchedules,
    selectedFacility,
    scheduleId: response.scheduleId,
    scheduleVersion: response.scheduleVersion,
    latestOptimization: protoSummaryToUI(response.latestOptimization),
    optimizationStats: protoStatsToUI(response.latestOptimizationStats),
    optimizationFinancials: protoFinancialsToUI(response.latestOptimizationFinancials),
    activeRun: protoOptimizationRunToUI(response.activeOptimizationRun),
    updatedAt: response.updatedAt || null,
  };
}

export default function useScheduleQuery(anchorDate: Date) {
  const { replaceScheduleData, setScheduleData } = useSchedulingStore(
    useShallow((state) => ({
      replaceScheduleData: state.replaceScheduleData,
      setScheduleData: state.setScheduleData,
    })),
  );

  const startDate = new Date(anchorDate);
  startDate.setDate(startDate.getDate() - 2);
  const endDate = new Date(startDate);
  endDate.setDate(endDate.getDate() + 5);

  const queryKey: ScheduleQueryKey = {
    startDate: formatDateYYYMMDD(startDate),
    endDate: formatDateYYYMMDD(endDate),
  };

  const query = useQuery({
    queryKey: ["schedule", queryKey],
    queryFn: () => fetchScheduleData(queryKey),
    staleTime: 5 * 1000,
  });

  useEffect(() => {
    if (query.status === "success") {
      replaceScheduleData({
        map: query.data.scheduleMap,
        facility: query.data.selectedFacility,
        scheduleId: query.data.scheduleId,
        scheduleVersion: query.data.scheduleVersion,
        latestOptimization: query.data.latestOptimization,
        optimizationStats: query.data.optimizationStats,
        optimizationFinancials: query.data.optimizationFinancials,
        activeRun: query.data.activeRun,
        updatedAt: query.data.updatedAt,
      });
    } else if (query.status === "error") {
      setScheduleData(new Map(), false, query.error as Error, null);
    } else if (query.status === "pending") {
      setScheduleData(new Map(), true, null, null);
    }
  }, [
    query.status,
    query.isFetching,
    query.data,
    query.error,
    replaceScheduleData,
    setScheduleData,
  ]);

  return {
    data: query.data,
    isFetching: query.isFetching,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

export { protoSummaryToUI };
