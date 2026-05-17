import type { StateCreator } from "zustand";
import { UIDraftState, UIStagedPatch, UIPatchConflict } from "@/types/scheduling";
import { applyPatchToMap } from "@/lib/scheduling-helpers";
import { FullSchedulingState } from "./state-types";

export const emptyDraftState = (): UIDraftState => ({
  baseScheduleVersion: 0,
  patches: [],
  conflicts: [],
  hasPendingValidation: false,
});

export interface DraftSlice {
  draftState: UIDraftState;

  setDraftPatches: (patches: UIStagedPatch[], conflicts?: UIPatchConflict[]) => void;
  appendDraftPatch: (patch: UIStagedPatch) => void;
  clearDraft: () => void;
  setDraftConflicts: (conflicts: UIPatchConflict[]) => void;
  setHasPendingValidation: (hasPendingValidation: boolean) => void;
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
      return {
        draftState: nextDraft,
        effectiveScheduleMap: new Map(serverMap),
      };
    });
  },

  setDraftConflicts: (conflicts) => {
    set((state) => {
      const nextDraft = { ...state.draftState, conflicts, hasPendingValidation: false };
      return { draftState: nextDraft };
    });
  },

  setHasPendingValidation: (hasPendingValidation) => {
    set((state) => {
      const nextDraft = { ...state.draftState, hasPendingValidation };
      return { draftState: nextDraft };
    });
  },
});
