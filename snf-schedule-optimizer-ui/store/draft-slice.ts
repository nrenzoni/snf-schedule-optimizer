import type { StateCreator } from "zustand";
import { UIDraftState, UIStagedPatch, UIPatchConflict } from "@/types/scheduling";
import { applyPatchToMap } from "@/lib/scheduling-helpers";
import { emptyDraftState, persistDraftState, readPersistedState } from "./persistence";
import { FullSchedulingState } from "./state-types";

export interface DraftSlice {
  draftState: UIDraftState;

  setDraftPatches: (patches: UIStagedPatch[], conflicts?: UIPatchConflict[]) => void;
  appendDraftPatch: (patch: UIStagedPatch) => void;
  clearDraft: () => void;
  setDraftConflicts: (conflicts: UIPatchConflict[]) => void;
  setHasPendingValidation: (hasPendingValidation: boolean) => void;
  hydratePersistedDraftState: () => void;
}

export const createDraftSlice: StateCreator<
  FullSchedulingState,
  [],
  [],
  DraftSlice
> = (set) => ({
  draftState: emptyDraftState(),

  setDraftPatches: (patches, conflicts = []) => {
    set((state) => {
      const currentDraft = state.draftState;
      const serverMap = state.serverScheduleMap;
      const scheduleVersion = state.scheduleVersion ?? 0;
      const nextDraft: UIDraftState = {
        ...currentDraft,
        baseScheduleVersion: currentDraft.baseScheduleVersion || scheduleVersion,
        patches,
        conflicts,
        hasPendingValidation: false,
      };
      persistDraftState(nextDraft, state.activeRun);
      return {
        draftState: nextDraft,
        effectiveScheduleMap: applyPatchToMap(serverMap, patches),
      };
    });
  },

  appendDraftPatch: (patch) => {
    set((state) => {
      const currentDraft = state.draftState;
      const serverMap = state.serverScheduleMap;
      const scheduleVersion = state.scheduleVersion ?? 0;
      const patches = [...currentDraft.patches, patch];
      const nextDraft: UIDraftState = {
        ...currentDraft,
        baseScheduleVersion: currentDraft.baseScheduleVersion || scheduleVersion,
        patches,
        hasPendingValidation: false,
      };
      persistDraftState(nextDraft, state.activeRun);
      return {
        draftState: nextDraft,
        effectiveScheduleMap: applyPatchToMap(serverMap, patches),
      };
    });
  },

  clearDraft: () => {
    set((state) => {
      const serverMap = state.serverScheduleMap;
      const scheduleVersion = state.scheduleVersion ?? 0;
      const nextDraft: UIDraftState = {
        baseScheduleVersion: scheduleVersion,
        patches: [],
        conflicts: [],
        hasPendingValidation: false,
      };
      persistDraftState(nextDraft, state.activeRun);
      return {
        draftState: nextDraft,
        effectiveScheduleMap: new Map(serverMap),
        hasNewerVersion: false,
      };
    });
  },

  setDraftConflicts: (conflicts) => {
    set((state) => {
      const nextDraft = { ...state.draftState, conflicts, hasPendingValidation: false };
      persistDraftState(nextDraft, state.activeRun);
      return { draftState: nextDraft };
    });
  },

  setHasPendingValidation: (hasPendingValidation) => {
    set((state) => {
      const nextDraft = { ...state.draftState, hasPendingValidation };
      persistDraftState(nextDraft, state.activeRun);
      return { draftState: nextDraft };
    });
  },

  hydratePersistedDraftState: () => {
    set((state) => {
      if (state.hasHydratedDraftState) return state;
      const persisted = readPersistedState();
      const effectiveScheduleMap = applyPatchToMap(
        state.serverScheduleMap,
        persisted.draft.patches,
      );
      return {
        draftState: persisted.draft,
        activeRun: persisted.activeRun as FullSchedulingState["activeRun"],
        effectiveScheduleMap,
        hasHydratedDraftState: true,
      };
    });
  },
});
