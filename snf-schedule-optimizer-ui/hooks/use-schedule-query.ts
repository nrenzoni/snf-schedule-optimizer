import { useQuery } from "@tanstack/react-query";
import { formatDateYYYMMDD } from "@/utils/scheduling-logic";
import { useSchedulingStore } from "@/store/schedulingStore";
import {
  ScheduleMap,
  UIDaySchedule,
  UIFinancials,
  UIOptimizationStats,
  UIOptimizationSummary,
  UINurse,
  UIShift,
} from "@/types/scheduling";
import { useShallow } from "zustand/react/shallow";
import {
  DaySchedule as ProtoDaySchedule,
  FinancialReport,
  Nurse as ProtoNurse,
  OptimizationStats,
  OptimizationSummary,
  OrgFacility,
  Shift as ProtoShift,
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
  };
}

export default function useScheduleQuery(anchorDate: Date) {
  const { replaceScheduleData, setScheduleData, setIsOptimizing } = useSchedulingStore(
    useShallow((state) => ({
      replaceScheduleData: state.replaceScheduleData,
      setScheduleData: state.setScheduleData,
      setIsOptimizing: state.setIsOptimizing,
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
    if (!query.isFetching) {
      setIsOptimizing(false);
    }

    if (query.status === "success") {
      replaceScheduleData(
        query.data.scheduleMap,
        query.data.selectedFacility,
        query.data.scheduleId,
        query.data.scheduleVersion,
        query.data.latestOptimization,
      );
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
    setIsOptimizing,
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
