import type { StateCreator } from "zustand";
import { UIOptimizationRun, UIDraftState } from "@/types/scheduling";
import { FullSchedulingState } from "./state-types";

export interface RunSlice {
  activeRun: UIOptimizationRun | null;

  setActiveRun: (run: UIOptimizationRun | null) => void;
  setRunProgress: (run: UIOptimizationRun) => void;
}

export const createRunSlice: StateCreator<
  FullSchedulingState,
  [],
  [],
  RunSlice
> = (set) => ({
  activeRun: null,

  setActiveRun: (run) => {
    set(() => {
      return { activeRun: run };
    });
  },

  setRunProgress: (run) => {
    set((state) => {
      const completed = run.status === "completed";
      const nextDraft: UIDraftState = completed
        ? {
            baseScheduleVersion: run.resultScheduleVersion ?? state.scheduleVersion,
            patches: [],
            conflicts: [],
            hasPendingValidation: false,
          }
        : state.draftState;
      return {
        activeRun: run,
        latestOptimization: completed ? run.summary : state.latestOptimization,
        optimizationStats: completed ? run.stats : state.optimizationStats,
        optimizationFinancials: completed ? run.financials : state.optimizationFinancials,
        draftState: nextDraft,
      };
    });
  },
});
