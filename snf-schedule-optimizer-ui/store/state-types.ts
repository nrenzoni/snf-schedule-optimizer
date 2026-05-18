import { OrgFacility } from "@/gen/scheduling/v1/scheduling_pb";
import { RunHistoryEntry, ScheduleMap, UIDaySchedule, UIDraftState, UIFinancials, UIOptimizationRun, UIOptimizationStats, UIOptimizationSummary, UIStagedPatch, UISchedulerSettings } from "@/types/scheduling";

export interface PendingRunCapture {
  preSchedule: Record<string, UIDaySchedule>;
  stagedPatches: UIStagedPatch[];
}

export interface FullSchedulingState {
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
  pendingRunCapture: PendingRunCapture | null;
  completedRuns: RunHistoryEntry[];
  hasHydratedDraftState: boolean;
}
