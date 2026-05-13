import { create } from "zustand";
import { OrgFacility } from "@/gen/scheduling/v1/scheduling_pb";
import {
  ScheduleMap,
  UIFinancials,
  UIOptimizationStats,
  UIOptimizationSummary,
  UISchedulerSettings,
} from "@/types/scheduling";

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

interface SchedulingState {
  scheduleMap: ScheduleMap;
  isDataLoading: boolean;
  dataError: Error | null;
  selectedFacility: OrgFacility | null;
  isOptimizing: boolean;
  scheduleId: string | null;
  scheduleVersion: number;
  latestOptimization: UIOptimizationSummary | null;
  optimizationStats: UIOptimizationStats | null;
  optimizationFinancials: UIFinancials | null;
  schedulerSettings: UISchedulerSettings;

  setScheduleData: (
    map: ScheduleMap,
    isLoading: boolean,
    error: Error | null,
    facility?: OrgFacility | null,
  ) => void;
  replaceScheduleData: (
    map: ScheduleMap,
    facility: OrgFacility | null,
    scheduleId: string | null,
    scheduleVersion: number,
    latestOptimization: UIOptimizationSummary | null,
  ) => void;
  setOptimizeResult: (
    map: ScheduleMap,
    facility: OrgFacility | null,
    scheduleId: string | null,
    scheduleVersion: number,
    latestOptimization: UIOptimizationSummary | null,
    optimizationStats: UIOptimizationStats | null,
    optimizationFinancials: UIFinancials | null,
  ) => void;
  setIsOptimizing: (status: boolean) => void;
  setSchedulerSettings: (settings: UISchedulerSettings) => void;
  resetDemoState: () => void;
}

export const useSchedulingStore = create<SchedulingState>((set) => ({
  scheduleMap: new Map(),
  isDataLoading: false,
  dataError: null,
  selectedFacility: null,
  isOptimizing: false,
  scheduleId: null,
  scheduleVersion: 0,
  latestOptimization: null,
  optimizationStats: null,
  optimizationFinancials: null,
  schedulerSettings: defaultSchedulerSettings,

  setScheduleData: (map, isLoading, error, facility = null) => {
    set((state) => ({
      scheduleMap: isLoading ? state.scheduleMap : map,
      isDataLoading: isLoading,
      dataError: error,
      selectedFacility: facility ?? state.selectedFacility,
    }));
  },

  replaceScheduleData: (map, facility, scheduleId, scheduleVersion, latestOptimization) => {
    set((state) => ({
      scheduleMap: map,
      isDataLoading: false,
      dataError: null,
      selectedFacility: facility ?? state.selectedFacility,
      scheduleId,
      scheduleVersion,
      latestOptimization,
    }));
  },

  setOptimizeResult: (
    map,
    facility,
    scheduleId,
    scheduleVersion,
    latestOptimization,
    optimizationStats,
    optimizationFinancials,
  ) => {
    set((state) => ({
      scheduleMap: map,
      isDataLoading: false,
      dataError: null,
      selectedFacility: facility ?? state.selectedFacility,
      scheduleId,
      scheduleVersion,
      latestOptimization,
      optimizationStats,
      optimizationFinancials,
      isOptimizing: false,
    }));
  },

  setIsOptimizing: (status) => set({ isOptimizing: status }),
  setSchedulerSettings: (settings) => set({ schedulerSettings: settings }),
  resetDemoState: () =>
    set({
      scheduleMap: new Map(),
      isDataLoading: false,
      dataError: null,
      selectedFacility: null,
      isOptimizing: false,
      scheduleId: null,
      scheduleVersion: 0,
      latestOptimization: null,
      optimizationStats: null,
      optimizationFinancials: null,
      schedulerSettings: defaultSchedulerSettings,
    }),
}));
