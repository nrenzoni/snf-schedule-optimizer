import { create } from "zustand";
import { UISchedulerSettings } from "@/types/scheduling";
import { clearPersistedState } from "./persistence";
import { createScheduleDataSlice, ScheduleDataSlice } from "./schedule-data-slice";
import { createDraftSlice, DraftSlice } from "./draft-slice";
import { createRunSlice, RunSlice } from "./run-slice";
import { emptyDraftState } from "./persistence";

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

export const useSchedulingStore = create<SchedulingState>()((set, get, ...rest) => ({
  ...createScheduleDataSlice(set, get, ...rest),
  ...createDraftSlice(set, get, ...rest),
  ...createRunSlice(set, get, ...rest),
  hasHydratedDraftState: false,
  resetDemoState: () => {
    clearPersistedState();
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
}));
