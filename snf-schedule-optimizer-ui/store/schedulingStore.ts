import { create } from "zustand";
import { OrgFacility } from "@/gen/scheduling/v1/scheduling_pb";
import { ScheduleMap } from "@/types/scheduling";

// --- Placeholder for Mock Hooks (replace with real API calls later) ---
// NOTE: In a real app, the data fetching logic would be integrated here or via middleware.
// For this refactor, we simulate the state management portion.

interface SchedulingState {
  // --- DATA STATE ---
  // The raw schedule data fetched by TanStack Query
  scheduleMap: ScheduleMap;
  isDataLoading: boolean;
  dataError: Error | null;
  selectedFacility: OrgFacility | null;

  // --- GLOBAL APP STATE ---
  // Optimization flags used by loaders/spinners and query keys
  isOptimized: boolean;
  isOptimizing: boolean;

  // --- ACTIONS ---
  // Simple setters. Complex logic lives in Hooks now.
  setScheduleData: (
    map: ScheduleMap,
    isLoading: boolean,
    error: Error | null,
    facility?: OrgFacility | null,
  ) => void;
  mergeScheduleData: (
    map: ScheduleMap,
    isLoading: boolean,
    error: Error | null,
    facility?: OrgFacility | null,
  ) => void;

  setIsOptimizing: (status: boolean) => void;
  setIsOptimized: (status: boolean) => void;
  resetDemoState: () => void;
}

export const useSchedulingStore = create<SchedulingState>((set) => ({
  // --- Initial State ---
  scheduleMap: new Map(),
  isDataLoading: false,
  dataError: null,
  selectedFacility: null,
  isOptimized: false,
  isOptimizing: false,

  // Actions
  setScheduleData: (map, isLoading, error, facility = null) => {
    set({
      scheduleMap: map,
      isDataLoading: isLoading,
      dataError: error,
      selectedFacility: facility,
    });
  },

  mergeScheduleData: (map, isLoading, error, facility = null) => {
    set((state) => {
      const scheduleMap = new Map(state.scheduleMap);
      map.forEach((schedule, date) => scheduleMap.set(date, schedule));
      return {
        scheduleMap,
        isDataLoading: isLoading,
        dataError: error,
        selectedFacility: facility ?? state.selectedFacility,
      };
    });
  },

  setIsOptimized: (status) => set({ isOptimized: status }),
  setIsOptimizing: (status) => set({ isOptimizing: status }),
  resetDemoState: () =>
    set({
      scheduleMap: new Map(),
      isDataLoading: false,
      dataError: null,
      selectedFacility: null,
      isOptimized: false,
      isOptimizing: false,
    }),
}));
