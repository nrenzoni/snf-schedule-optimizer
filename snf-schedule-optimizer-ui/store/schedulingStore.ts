import { create } from "zustand";
import { persist } from "zustand/middleware";
import { UISchedulerSettings, UIDraftState } from "@/types/scheduling";
import { createScheduleDataSlice, ScheduleDataSlice } from "./schedule-data-slice";
import { createDraftSlice, DraftSlice } from "./draft-slice";
import { createRunSlice, RunSlice } from "./run-slice";

export const emptyDraftState = (): UIDraftState => ({
  baseScheduleVersion: 0,
  patches: [],
  conflicts: [],
  hasPendingValidation: false,
});

export const defaultSchedulerSettings: UISchedulerSettings = {
  useMLForecast: false,
  useCalloutBuffer: true,
  bufferThreshold: 10,
  minRestPeriod: 10,
  maxShiftLength: 12,
  premiumWeekend: true,
  premiumHoliday: false,
  overtimeAvoidancePenalty: 1000,
  teamConsistencyPenalty: 300,
  highRiskShiftPenalty: 2000,
  customPreferencePenalty: 1500,
};

interface SchedulingState extends ScheduleDataSlice, DraftSlice, RunSlice {
  hasHydratedDraftState: boolean;
  resetDemoState: () => void;
}

export const useSchedulingStore = create<SchedulingState>()(
  persist(
    (set, get, ...rest) => ({
      ...createScheduleDataSlice(set, get, ...rest),
      ...createDraftSlice(set, get, ...rest),
      ...createRunSlice(set, get, ...rest),
      hasHydratedDraftState: false,
      resetDemoState: () => {
        useSchedulingStore.persist.clearStorage();
        set({
          serverScheduleMap: new Map(),
          effectiveScheduleMap: new Map(),
          isDataLoading: false,
          dataError: null,
          selectedFacility: null,
          scheduleId: null,
          scheduleVersion: 0,
          latestOptimization: null,
          optimizationStats: null,
          optimizationFinancials: null,
          schedulerSettings: defaultSchedulerSettings,
          hasNewerVersion: false,
          latestKnownScheduleVersion: 0,
          draftState: emptyDraftState(),
          activeRun: null,
          hasHydratedDraftState: false,
        });
      },
    }),
    {
      name: "snf-scheduling-store",
      version: 1,
      partialize: (state) => ({
        draftState: state.draftState,
        activeRun: state.activeRun,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.hasHydratedDraftState = true;
        }
      },
    }
  )
);
