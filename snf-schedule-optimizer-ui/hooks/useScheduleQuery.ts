import {useQuery} from "@tanstack/react-query";
import {generateMockScheduleMap, getStartOfMonth, getStartOfWeek} from '@/utils/scheduling-logic';
import {useSchedulingStore} from '@/store/schedulingStore';
import {UIDaySchedule} from '@/types/scheduling';
import {useShallow} from "zustand/react/shallow";

// Define the shape of the query key for type safety
interface ScheduleQueryKey {
    anchorMonth: string; // YYYY-MM
    isOptimized: boolean; // Optimization state for mock data generation
}

// Data fetching function that simulates the API call
async function fetchScheduleData({anchorMonth, isOptimized}: ScheduleQueryKey): Promise<Map<string, UIDaySchedule>> {
    console.log(`Fetching schedule for month: ${anchorMonth}, Optimized: ${isOptimized}`);

    // 1. Simulate Network Latency
    await new Promise(resolve => setTimeout(resolve, 500));

    // 2. Determine the start of the 42-day calendar grid based on the anchor month
    // We only need the month, not the day of the week, for the anchor.
    const anchorDate = new Date(anchorMonth);
    const startOfGrid = getStartOfWeek(getStartOfMonth(anchorDate));

    // 3. Generate the mock data (42 days covers any calendar grid)
    const mockMap = generateMockScheduleMap(startOfGrid, 42);

    return mockMap;
}


export const useScheduleQuery = () => {
    // 1. Get current data anchor and optimization state from the store
    const {currentDate, isOptimized, setScheduleData} = useSchedulingStore(useShallow(state => ({
        currentDate: state.currentDate,
        isOptimized: state.isOptimized,
        setScheduleData: state.setScheduleData,
    })));

    // 2. Derive a stable query key based on the month and optimization status
    const queryKey: ScheduleQueryKey = {
        anchorMonth: `${currentDate.getFullYear()}-${(currentDate.getMonth() + 1).toString().padStart(2, '0')}`,
        isOptimized: isOptimized,
    };

    // 3. Use TanStack Query to manage fetching, caching, and state
    const query = useQuery({
        queryKey: ['schedule', queryKey],
        queryFn: () => fetchScheduleData(queryKey),
        // Keep stale time low for demonstration
        staleTime: 5 * 1000,
        // Refetch whenever the key changes (i.e., month changes OR optimization state changes)
        enabled: true,

        // 4. On successful fetch, update the Zustand store
        onSuccess: (data) => {
            setScheduleData(data, false, null);
        },
        onError: (error) => {
            console.error("Schedule query failed:", error);
            setScheduleData(new Map(), false, error as Error);
        },
    });

    // We expose the query status but the data flows directly into Zustand
    return {
        isFetching: query.isFetching,
        isLoading: query.isLoading,
        error: query.error,
        // We do NOT return the data map itself
    };
};