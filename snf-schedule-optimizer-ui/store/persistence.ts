import { UIDraftState } from "@/types/scheduling";

export const STORAGE_KEY = "snf-scheduling-draft-v1";

export const emptyDraftState = (): UIDraftState => ({
  baseScheduleVersion: 0,
  patches: [],
  conflicts: [],
  hasPendingValidation: false,
});

export const persistDraftState = (
  draft: UIDraftState,
  activeRun: unknown,
) => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ draft, activeRun }));
};

export const readPersistedState = (): {
  activeRun: unknown;
  draft: UIDraftState;
} => {
  if (typeof window === "undefined") {
    return { activeRun: null, draft: emptyDraftState() };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { activeRun: null, draft: emptyDraftState() };
    }
    const parsed = JSON.parse(raw) as { activeRun?: unknown; draft?: UIDraftState };
    return {
      activeRun: parsed.activeRun ?? null,
      draft: parsed.draft ?? emptyDraftState(),
    };
  } catch {
    return { activeRun: null, draft: emptyDraftState() };
  }
};

export const clearPersistedState = () => {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(STORAGE_KEY);
  }
};
