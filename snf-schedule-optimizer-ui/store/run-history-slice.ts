import type { StateCreator } from "zustand";
import { RunHistoryEntry, UIDaySchedule } from "@/types/scheduling";
import { FullSchedulingState, PendingRunCapture } from "./state-types";

export const MAX_RUN_HISTORY = 10;

export interface RunHistorySlice {
  completedRuns: RunHistoryEntry[];
  pendingRunCapture: PendingRunCapture | null;

  setPendingRunCapture: (capture: PendingRunCapture | null) => void;
  updateRunPostSchedule: (runId: string, postSchedule: Record<string, UIDaySchedule>) => void;
}

export const createRunHistorySlice: StateCreator<
  FullSchedulingState,
  [],
  [],
  RunHistorySlice
> = (set) => ({
  completedRuns: [],
  pendingRunCapture: null,

  setPendingRunCapture: (capture) => {
    set({ pendingRunCapture: capture });
  },

  updateRunPostSchedule: (runId, postSchedule) => {
    set((state) => ({
      completedRuns: state.completedRuns.map((r) =>
        r.run.runId === runId ? { ...r, postSchedule } : r,
      ),
    }));
  },
});
