import { useQuery } from "@tanstack/react-query";
import {
  formatDateYYYMMDD,
  getStartOfMonth,
} from "@/utils/scheduling-logic";
import { useSchedulingStore } from "@/store/schedulingStore";
import { ScheduleMap, UIDaySchedule, UINurse, UIShift } from "@/types/scheduling";
import { useShallow } from "zustand/react/shallow";
import {
  DaySchedule as ProtoDaySchedule,
  Nurse as ProtoNurse,
  OrgFacility,
  Shift as ProtoShift,
} from "@/gen/scheduling/v1/scheduling_pb";
import { schedulingClient } from "@/api/scheduling-client";
import { useEffect } from "react";

type ScheduleQueryErrorCode =
  | "NO_FACILITIES"
  | "API_UNAVAILABLE"
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
  shiftHours: nurse.shiftHours,
  schedulingRationale: nurse.schedulingRationale,
});

const protoShiftToUI = (p: ProtoShift): UIShift => ({
  shiftName: p.shiftName as UIShift["shiftName"],
  patientCount: p.patientCensus,
  requiredHPRD: p.targetHrpd ?? 0,
  requiredHours: (p.patientCensus ?? 0) * (p.targetHrpd ?? 0),
  actualHours: (p.patientCensus ?? 0) * (p.actualHrpd ?? 0),
  isHPRDMet: p.isHrpdMet ?? false,
  nurses: (p.nurses || []).map(protoNurseToUI),
});

const protoDayToUI = (d: ProtoDaySchedule): UIDaySchedule => ({
  date: d.date,
  shifts: (d.shifts || []).map(protoShiftToUI),
});

// Define the shape of the query key for type safety
interface ScheduleQueryKey {
  anchorMonth: string; // YYYY-MM
  isOptimized: boolean; // Optimization state for mock data generation
}

async function fetchScheduleData({
  anchorMonth,
}: ScheduleQueryKey): Promise<{
  scheduleMap: ScheduleMap;
  selectedFacility: OrgFacility;
}> {
  const anchorDate = new Date(anchorMonth);
  const facilities = await schedulingClient.getAllOrgFacilities({}).catch(
    (error) => {
      throw new ScheduleQueryError(
        error instanceof Error
          ? error.message
          : "The scheduling API is unavailable.",
        "API_UNAVAILABLE",
      );
    },
  );
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
    startDate: formatDateYYYMMDD(getStartOfMonth(anchorDate)),
  });

  const newSchedules = new Map<string, UIDaySchedule>();
  Object.entries(response.schedules).forEach(([dateStr, schedule]) => {
    newSchedules.set(dateStr, protoDayToUI(schedule as ProtoDaySchedule));
  });
  return { scheduleMap: newSchedules, selectedFacility };
}

export default function useScheduleQuery(anchorDate: Date) {
  // 1. Get current data anchor and optimization state from the store
  const { isOptimized, setScheduleData, setIsOptimizing } = useSchedulingStore(
    useShallow((state) => ({
      isOptimized: state.isOptimized,
      setScheduleData: state.setScheduleData,
      // 1. Get the spinner setter
      setIsOptimizing: state.setIsOptimizing,
    })),
  );

  // 2. Derive a stable query key based on the month and optimization status
  const queryKey: ScheduleQueryKey = {
    anchorMonth: `${anchorDate.getFullYear()}-${(anchorDate.getMonth() + 1).toString().padStart(2, "0")}`,
    isOptimized: isOptimized,
  };

  // 3. Use TanStack Query to manage fetching, caching, and state
  const query = useQuery({
    queryKey: ["schedule", queryKey],
    queryFn: () => fetchScheduleData(queryKey),
    // Keep stale time low for demonstration
    staleTime: 5 * 1000,
    // Refetch whenever the key changes (i.e., month changes OR optimization state changes)
    // enabled: true,
  });

  // 4. Sync to Zustand (The "Effect" Pattern)
  // This replaces onSuccess/onError which are deprecated/removed in v5
  useEffect(() => {
    if (!query.isFetching) {
      setIsOptimizing(false);
    }

    if (query.status === "success") {
      setScheduleData(
        query.data.scheduleMap,
        false,
        null,
        query.data.selectedFacility,
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
    setScheduleData,
    setIsOptimizing,
  ]);

  // We expose the query status but the data flows directly into Zustand
  return {
    data: query.data,
    isFetching: query.isFetching,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}
