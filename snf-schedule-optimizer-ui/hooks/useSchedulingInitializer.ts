import {useScheduleQuery} from './useScheduleQuery';
import {useSchedulingStore} from '@/store/schedulingStore';
import {useShallow} from "zustand/react/shallow";

/**
 * Hook to initialize the scheduling data flow by running the schedule query
 * and managing initial calculation.
 */
export const useSchedulingInitializer = () => {

    // Run the TanStack Query hook (This handles fetching and syncing to Zustand)
    const { isLoading, isFetching, error } = useScheduleQuery();

    // const { scheduleMap } = useSchedulingStore(
    //     useShallow(state => ({
    //         scheduleMap: state.scheduleMap,
    //     }))
    // );

    // Expose the core loading status
    return {
        isAppLoading: isLoading || isFetching,
        error,
    };
};