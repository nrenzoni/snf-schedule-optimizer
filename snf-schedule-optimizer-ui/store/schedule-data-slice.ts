import type { StateCreator } from "zustand";
import { OrgFacility } from "@/gen/scheduling/v1/scheduling_pb";
import {
  ScheduleMap,
  UIFinancials,
  UIOptimizationStats,
  UIOptimizationSummary,
  UISchedulerSettings,
} from "@/types/scheduling";
import { defaultSchedulerSettings } from "./schedulingStore";
import { applyPatchToMap } from "@/lib/scheduling-helpers";
import { FullSchedulingState } from "./state-types";

export interface ScheduleDataSlice {
  serverScheduleMap: ScheduleMap;
  effectiveScheduleMap: ScheduleMap;
  isDataLoading: boolean;
  dataError: Error | null;
  selectedFacility: OrgFacility | null;
  scheduleId: string | null;
  scheduleVersion: number;
  latestOptimization: UIOptimizationSummary | null;
  optimizationStats: UIOptimizationStats | null;
  optimizationFinancials: UIFinancials | null;
  schedulerSettings: UISchedulerSettings;
  hasNewerVersion: boolean;
  latestKnownScheduleVersion: number;

  setScheduleData: (
    map: ScheduleMap,
    isLoading: boolean,
    error: Error | null,
    facility?: OrgFacility | null,
  ) => void;
  replaceScheduleData: (payload: {
    map: ScheduleMap;
    facility: OrgFacility | null;
    scheduleId: string | null;
    scheduleVersion: number;
    latestOptimization: UIOptimizationSummary | null;
    optimizationStats: UIOptimizationStats | null;
    optimizationFinancials: UIFinancials | null;
    activeRun: import("@/types/scheduling").UIOptimizationRun | null;
    updatedAt: string | null;
  }) => void;
  setHasNewerVersion: (hasNewerVersion: boolean, latestKnownScheduleVersion?: number) => void;
  setSchedulerSettings: (settings: UISchedulerSettings) => void;
}

export const createScheduleDataSlice: StateCreator<
  FullSchedulingState,
  [],
  [],
  ScheduleDataSlice
> = (set) => ({
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

  setScheduleData: (map, isLoading, error, facility = null) => {
    set((state) => ({
      serverScheduleMap: isLoading ? state.serverScheduleMap : map,
      effectiveScheduleMap: isLoading
        ? state.effectiveScheduleMap
        : applyPatchToMap(map, state.draftState?.patches ?? []),
      isDataLoading: isLoading,
      dataError: error,
      selectedFacility: facility ?? state.selectedFacility,
    }));
  },

  replaceScheduleData: ({
    map,
    facility,
    scheduleId,
    scheduleVersion,
    latestOptimization,
    optimizationStats,
    optimizationFinancials,
    activeRun,
  }) => {
    set((state) => {
      const draft = state.draftState;
      const draftBaseVersion = draft?.baseScheduleVersion ?? 0;
      const hasNewerVersion =
        draftBaseVersion > 0 &&
        draftBaseVersion !== scheduleVersion &&
        (draft?.patches ?? []).length > 0;
      const draftState = hasNewerVersion
        ? draft
        : {
            ...draft,
            baseScheduleVersion:
              (draft?.patches ?? []).length > 0
                ? (draft?.baseScheduleVersion || scheduleVersion)
                : scheduleVersion,
          };
      const effectiveScheduleMap = hasNewerVersion
        ? new Map(map)
        : applyPatchToMap(map, draftState?.patches ?? []);
      return {
        serverScheduleMap: map,
        effectiveScheduleMap,
        isDataLoading: false,
        dataError: null,
        selectedFacility: facility ?? state.selectedFacility,
        scheduleId,
        scheduleVersion,
        latestKnownScheduleVersion: scheduleVersion,
        latestOptimization,
        optimizationStats,
        optimizationFinancials,
        hasNewerVersion,
        draftState,
        activeRun,
      };
    });
  },

  setHasNewerVersion: (hasNewerVersion, latestKnownScheduleVersion) => {
    set((state) => ({
      hasNewerVersion,
      latestKnownScheduleVersion:
        latestKnownScheduleVersion ?? state.latestKnownScheduleVersion,
    }));
  },

  setSchedulerSettings: (settings) => set({ schedulerSettings: settings }),
});
