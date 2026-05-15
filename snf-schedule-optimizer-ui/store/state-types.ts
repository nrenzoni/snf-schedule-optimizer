import { OrgFacility } from "@/gen/scheduling/v1/scheduling_pb";
import { ScheduleMap, UIDraftState, UIFinancials, UIOptimizationRun, UIOptimizationStats, UIOptimizationSummary, UISchedulerSettings } from "@/types/scheduling";

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
  hasHydratedDraftState: boolean;
}
