import { create } from "zustand";
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
  ) => void;

  setIsOptimizing: (status: boolean) => void;
  setIsOptimized: (status: boolean) => void;
}

export const useSchedulingStore = create<SchedulingState>((set, get) => ({
  // --- Initial State ---
  scheduleMap: new Map(),
  isDataLoading: false,
  dataError: null,
  isOptimized: false,
  isOptimizing: false,

  // Actions
  setScheduleData: (map, isLoading, error) => {
    set({
      scheduleMap: map,
      isDataLoading: isLoading,
      dataError: error,
    });
  },

  setIsOptimized: (status) => set({ isOptimized: status }),
  setIsOptimizing: (status) => set({ isOptimizing: status }),
}));
