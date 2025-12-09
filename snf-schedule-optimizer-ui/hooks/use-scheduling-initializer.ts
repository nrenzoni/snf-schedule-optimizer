import { useIsFetching } from "@tanstack/react-query";

/**
 * A lightweight hook to check if the schedule is currently loading/refetching
 * anywhere in the app.
 */
export function useSchedulingInitializer() {
  // Checks if any query with the key ["schedule"] is currently active
  const isFetching = useIsFetching({ queryKey: ["schedule"] });

  return {
    isAppLoading: isFetching > 0,
    error: null, // Global error handling is usually done at the QueryBoundary or Toast level
  };
}
