import { create } from "zustand";
import { OrgFacility } from "@/gen/scheduling/v1/scheduling_pb";
import {
  ScheduleMap,
  UIDraftState,
  UIFinancials,
  UIOptimizationRun,
  UIOptimizationStats,
  UIOptimizationSummary,
  UIPatchConflict,
  UIStagedPatch,
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

const STORAGE_KEY = "snf-scheduling-draft-v1";

const emptyDraftState = (): UIDraftState => ({
  baseScheduleVersion: 0,
  patches: [],
  conflicts: [],
  hasPendingValidation: false,
});

const cloneMap = (map: ScheduleMap): ScheduleMap => new Map(map);

const readPersistedState = (): {
  activeRun: UIOptimizationRun | null;
  draft: UIDraftState;
} => {
  if (typeof window === "undefined") {
    return {
      activeRun: null,
      draft: emptyDraftState(),
    };
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      throw new Error("missing draft storage");
    }
    const parsed = JSON.parse(raw) as {
      activeRun?: UIOptimizationRun | null;
      draft?: UIDraftState;
    };
    return {
      activeRun: parsed.activeRun ?? null,
      draft: parsed.draft ?? emptyDraftState(),
    };
  } catch {
    return {
      activeRun: null,
      draft: emptyDraftState(),
    };
  }
};

const persistState = (draft: UIDraftState, activeRun: UIOptimizationRun | null) => {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ draft, activeRun }),
  );
};

const removeEmployeeFromShift = (map: ScheduleMap, employeeId: string, shiftId: string | null) => {
  if (!shiftId) return;
  for (const [date, day] of map.entries()) {
    const shifts = day.shifts.map((shift) => {
      if (shift.shiftId !== shiftId) return shift;
      return {
        ...shift,
        nurses: shift.nurses.filter((nurse) => nurse.id !== employeeId),
      };
    });
    map.set(date, { ...day, shifts });
  }
};

const addEmployeeToShift = (
  map: ScheduleMap,
  employeeId: string,
  shiftId: string | null,
  employeeName: string | null,
) => {
  if (!shiftId) return;
  for (const [date, day] of map.entries()) {
    const shifts = day.shifts.map((shift) => {
      if (shift.shiftId !== shiftId) return shift;
      if (shift.nurses.some((nurse) => nurse.id === employeeId)) {
        return shift;
      }
      const sourceNurse = Array.from(map.values())
        .flatMap((scheduleDay) => scheduleDay.shifts)
        .flatMap((scheduleShift) => scheduleShift.nurses)
        .find((nurse) => nurse.id === employeeId);
      return {
        ...shift,
        nurses: [
          ...shift.nurses,
          sourceNurse ?? {
            id: employeeId,
            name: employeeName ?? "Manual Assignment",
            role: "",
            shiftHours: 8,
            schedulingRationale: "Pinned manual assignment",
            isAgency: false,
          },
        ],
      };
    });
    map.set(date, { ...day, shifts });
  }
};

const applyPatchToMap = (serverScheduleMap: ScheduleMap, patches: UIStagedPatch[]): ScheduleMap => {
  const next = cloneMap(serverScheduleMap);
  for (const patch of patches) {
    removeEmployeeFromShift(next, patch.employeeId, patch.fromShiftId);
    addEmployeeToShift(next, patch.employeeId, patch.toShiftId, patch.employeeName);
  }
  return next;
};

interface SchedulingState {
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
  draftState: UIDraftState;
  activeRun: UIOptimizationRun | null;
  hasHydratedDraftState: boolean;

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
    activeRun: UIOptimizationRun | null;
    updatedAt: string | null;
  }) => void;
  setDraftPatches: (patches: UIStagedPatch[], conflicts?: UIPatchConflict[]) => void;
  appendDraftPatch: (patch: UIStagedPatch) => void;
  clearDraft: () => void;
  setDraftConflicts: (conflicts: UIPatchConflict[]) => void;
  setHasPendingValidation: (hasPendingValidation: boolean) => void;
  setActiveRun: (run: UIOptimizationRun | null) => void;
  setRunProgress: (run: UIOptimizationRun) => void;
  setHasNewerVersion: (hasNewerVersion: boolean, latestKnownScheduleVersion?: number) => void;
  setSchedulerSettings: (settings: UISchedulerSettings) => void;
  hydratePersistedDraftState: () => void;
  resetDemoState: () => void;
}

export const useSchedulingStore = create<SchedulingState>((set) => ({
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

  setScheduleData: (map, isLoading, error, facility = null) => {
    set((state) => ({
      serverScheduleMap: isLoading ? state.serverScheduleMap : map,
      effectiveScheduleMap: isLoading
        ? state.effectiveScheduleMap
        : applyPatchToMap(map, state.draftState.patches),
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
      const draftBaseVersion = state.draftState.baseScheduleVersion;
      const hasNewerVersion =
        draftBaseVersion > 0 && draftBaseVersion !== scheduleVersion && state.draftState.patches.length > 0;
      const draftState = hasNewerVersion
        ? state.draftState
        : {
            ...state.draftState,
            baseScheduleVersion:
              state.draftState.patches.length > 0
                ? state.draftState.baseScheduleVersion || scheduleVersion
                : scheduleVersion,
          };
      const effectiveScheduleMap = hasNewerVersion
        ? cloneMap(map)
        : applyPatchToMap(map, draftState.patches);
      persistState(draftState, activeRun ?? state.activeRun);
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
        activeRun: activeRun ?? state.activeRun,
        hasNewerVersion,
        draftState,
      };
    });
  },

  setDraftPatches: (patches, conflicts = []) => {
    set((state) => {
      const nextDraft = {
        ...state.draftState,
        baseScheduleVersion: state.draftState.baseScheduleVersion || state.scheduleVersion,
        patches,
        conflicts,
        hasPendingValidation: false,
      };
      persistState(nextDraft, state.activeRun);
      return {
        draftState: nextDraft,
        effectiveScheduleMap: applyPatchToMap(state.serverScheduleMap, patches),
      };
    });
  },

  appendDraftPatch: (patch) => {
    set((state) => {
      const patches = [...state.draftState.patches, patch];
      const nextDraft = {
        ...state.draftState,
        baseScheduleVersion: state.draftState.baseScheduleVersion || state.scheduleVersion,
        patches,
        hasPendingValidation: false,
      };
      persistState(nextDraft, state.activeRun);
      return {
        draftState: nextDraft,
        effectiveScheduleMap: applyPatchToMap(state.serverScheduleMap, patches),
      };
    });
  },

  clearDraft: () => {
    set((state) => {
      const nextDraft: UIDraftState = {
        baseScheduleVersion: state.scheduleVersion,
        patches: [],
        conflicts: [],
        hasPendingValidation: false,
      };
      persistState(nextDraft, state.activeRun);
      return {
        draftState: nextDraft,
        effectiveScheduleMap: cloneMap(state.serverScheduleMap),
        hasNewerVersion: false,
      };
    });
  },

  setDraftConflicts: (conflicts) => {
    set((state) => {
      const nextDraft = {
        ...state.draftState,
        conflicts,
        hasPendingValidation: false,
      };
      persistState(nextDraft, state.activeRun);
      return { draftState: nextDraft };
    });
  },

  setHasPendingValidation: (hasPendingValidation) => {
    set((state) => {
      const nextDraft = { ...state.draftState, hasPendingValidation };
      persistState(nextDraft, state.activeRun);
      return { draftState: nextDraft };
    });
  },

  setActiveRun: (run) => {
    set((state) => {
      persistState(state.draftState, run);
      return { activeRun: run };
    });
  },

  setRunProgress: (run) => {
    set((state) => {
      const completed = run.status === "completed";
      const nextDraft = completed
        ? {
            baseScheduleVersion: run.resultScheduleVersion ?? state.scheduleVersion,
            patches: [],
            conflicts: [],
            hasPendingValidation: false,
          }
        : state.draftState;
      persistState(nextDraft, run);
      return {
        activeRun: run,
        latestOptimization: completed ? run.summary : state.latestOptimization,
        optimizationStats: completed ? run.stats : state.optimizationStats,
        optimizationFinancials: completed ? run.financials : state.optimizationFinancials,
        draftState: nextDraft,
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

  hydratePersistedDraftState: () => {
    const persisted = readPersistedState();
    set((state) => {
      if (state.hasHydratedDraftState) {
        return state;
      }

      const effectiveScheduleMap = applyPatchToMap(
        state.serverScheduleMap,
        persisted.draft.patches,
      );

      return {
        draftState: persisted.draft,
        activeRun: persisted.activeRun,
        effectiveScheduleMap,
        hasHydratedDraftState: true,
      };
    });
  },

  resetDemoState: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(STORAGE_KEY);
    }
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
