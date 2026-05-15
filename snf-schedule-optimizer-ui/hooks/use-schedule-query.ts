import { useQuery } from "@tanstack/react-query";
import { formatDateYYYYMMDD } from "@/lib/scheduling-logic";
import { useSchedulingStore } from "@/store/schedulingStore";
import {
  ScheduleMap,
  UIDaySchedule,
  UIFinancials,
  UIOptimizationRun,
  UIOptimizationStats,
  UIOptimizationSummary,
} from "@/types/scheduling";
import { useShallow } from "zustand/react/shallow";
import {
  DaySchedule as ProtoDaySchedule,
  OrgFacility,
} from "@/gen/scheduling/v1/scheduling_pb";
import { configuredBaseUrl, schedulingClient } from "@/api/scheduling-client";
import { useEffect } from "react";
import {
  protoDayToUI,
  protoFinancialsToUI,
  protoOptimizationRunToUI,
  protoStatsToUI,
  protoSummaryToUI,
} from "@/lib/proto-mappers";

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
  const endDate = new Date(anchorDate);
  endDate.setDate(endDate.getDate() + 5);

  const queryKey: ScheduleQueryKey = {
    startDate: formatDateYYYYMMDD(startDate),
    endDate: formatDateYYYYMMDD(endDate),
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
