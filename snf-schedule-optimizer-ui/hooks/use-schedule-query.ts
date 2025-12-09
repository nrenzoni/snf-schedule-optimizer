import { useQuery } from "@tanstack/react-query";
import {
  formatDateYYYMMDD,
  generateMockScheduleMap,
  getStartOfMonth,
  getStartOfWeek,
} from "@/utils/scheduling-logic";
import { useSchedulingStore } from "@/store/schedulingStore";
import { UIDaySchedule } from "@/types/scheduling";
import { useShallow } from "zustand/react/shallow";
import { DaySchedule as ProtoDaySchedule } from "@/gen/schema/scheduling_pb";
import { schedulingClient } from "@/api/scheduling-client";
import { useEffect } from "react";

// Convert a protobuf DaySchedule/Shift into the UI DaySchedule/Shift shape
const protoShiftToUI = (p: any): any => ({
  shiftName: p.shiftName as any as "Morning" | "Afternoon" | "Night",
  patientCount: p.patientCount,
  requiredHPRD: p.requiredHrpd ?? 0,
  requiredHours: p.requiredHours,
  actualHours: p.actualHours,
  isHPRDMet: p.isHrpdMet ?? false,
  nurses: (p.nurses || []).map((n: any) => ({
    id: n.id,
    name: n.name,
    shiftHours: n.shiftHours,
    schedulingRationale: n.schedulingRationale,
  })),
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

// Data fetching function that simulates the API call
async function fetchScheduleData({
  anchorMonth,
  isOptimized,
}: ScheduleQueryKey): Promise<Map<string, UIDaySchedule>> {
  console.log(
    `Fetching schedule for month: ${anchorMonth}, Optimized: ${isOptimized}`,
  );

  const USE_REAL_API = false;

  if (USE_REAL_API) {
    const anchorDate = new Date(anchorMonth);
    const request = {
      startDate: formatDateYYYMMDD(getStartOfMonth(anchorDate)),
    };

    const response = await schedulingClient.getMonthlySchedule(request);

    const newSchedules = new Map<string, UIDaySchedule>();
    Object.entries(response.schedules).forEach(([dateStr, schedule]) => {
      newSchedules.set(dateStr, protoDayToUI(schedule as ProtoDaySchedule));
    });
    return newSchedules;
  }

  // --- MOCK FALLBACK ---

  // 1. Simulate Network Latency
  await new Promise((resolve) => setTimeout(resolve, 500));

  // 2. Determine the start of the 42-day calendar grid based on the anchor month
  // We only need the month, not the day of the week, for the anchor.
  const anchorDate = new Date(anchorMonth);
  const startOfGrid = getStartOfWeek(getStartOfMonth(anchorDate));

  // 3. Generate the mock data (42 days covers any calendar grid)
  return generateMockScheduleMap(startOfGrid, 42);
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
      setScheduleData(query.data, false, null);
    } else if (query.status === "error") {
      setScheduleData(new Map(), false, query.error as Error);
    } else if (query.status === "pending") {
      // Optional: Update loading state in store if needed,
      // though useScheduling usually handles this via isAppLoading
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
    isFetching: query.isFetching,
    isLoading: query.isLoading,
    error: query.error,
  };
}
