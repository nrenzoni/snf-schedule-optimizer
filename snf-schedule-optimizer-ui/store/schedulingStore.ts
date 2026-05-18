import { create } from "zustand";
import { persist } from "zustand/middleware";
import { UISchedulerSettings } from "@/types/scheduling";
import { createScheduleDataSlice, ScheduleDataSlice } from "./schedule-data-slice";
import { createDraftSlice, DraftSlice, emptyDraftState } from "./draft-slice";
import { createRunSlice, RunSlice } from "./run-slice";
import { createRunHistorySlice, RunHistorySlice } from "./run-history-slice";

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

interface SchedulingState extends ScheduleDataSlice, DraftSlice, RunSlice, RunHistorySlice {
  hasHydratedDraftState: boolean;
  resetDemoState: () => void;
}

export const useSchedulingStore = create<SchedulingState>()(
  persist(
    (set, get, ...rest) => ({
      ...createScheduleDataSlice(set, get, ...rest),
      ...createDraftSlice(set, get, ...rest),
      ...createRunSlice(set, get, ...rest),
      ...createRunHistorySlice(set, get, ...rest),
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
          pendingRunCapture: null,
          completedRuns: [],
          hasHydratedDraftState: false,
        });
      },
    }),
    {
      name: "snf-scheduling-store",
      version: 2,
      partialize: (state) => ({
        draftState: state.draftState,
        activeRun: state.activeRun,
        completedRuns: state.completedRuns,
        pendingRunCapture: state.pendingRunCapture,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.hasHydratedDraftState = true;
        }
      },
    }
  )
);
