import { useQuery } from "@tanstack/react-query";
import { formatDateYYYYMMDD } from "@/lib/scheduling-logic";
import {
  ScheduleMap,
  UIDaySchedule,
  UIFinancials,
  UIOptimizationRun,
  UIOptimizationStats,
  UIOptimizationSummary,
} from "@/types/scheduling";
import {
  DaySchedule as ProtoDaySchedule,
  OrgFacility,
} from "@/gen/scheduling/v1/scheduling_pb";
import { configuredBaseUrl, schedulingClient } from "@/api/scheduling-client";
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
  const startDate = new Date(anchorDate);
  startDate.setDate(startDate.getDate() - 2);
  const endDate = new Date(anchorDate);
  endDate.setDate(endDate.getDate() + 5);

  const queryKey: ScheduleQueryKey = {
    startDate: formatDateYYYYMMDD(startDate),
    endDate: formatDateYYYYMMDD(endDate),
  };

  return useQuery({
    queryKey: ["schedule", queryKey],
    queryFn: () => fetchScheduleData(queryKey),
    staleTime: 5 * 1000,
  });
}

export function useScheduleData(anchorDate: Date) {
  const query = useScheduleQuery(anchorDate);

  return {
    ...query,
    scheduleMap: query.data?.scheduleMap ?? new Map<string, UIDaySchedule>(),
    selectedFacility: query.data?.selectedFacility ?? null,
    scheduleId: query.data?.scheduleId ?? null,
    scheduleVersion: query.data?.scheduleVersion ?? 0,
    latestOptimization: query.data?.latestOptimization ?? null,
    optimizationStats: query.data?.optimizationStats ?? null,
    optimizationFinancials: query.data?.optimizationFinancials ?? null,
    activeRunRQ: query.data?.activeRun ?? null,
    updatedAt: query.data?.updatedAt ?? null,
  };
}
