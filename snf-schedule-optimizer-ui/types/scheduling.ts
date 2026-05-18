export interface UISchedulerSettings {
  useMLForecast: boolean;
  useCalloutBuffer: boolean;
  bufferThreshold: number;
  minRestPeriod: number;
  maxShiftLength: number;
  premiumWeekend: boolean;
  premiumHoliday: boolean;
  overtimeAvoidancePenalty: number;
  teamConsistencyPenalty: number;
  highRiskShiftPenalty: number;
  customPreferencePenalty: number;
}

export interface UIOptimizationSummary {
  assignmentsChanged: number;
  totalAssignments: number;
  coveredShifts: number;
  uncoveredShifts: number;
  completedAt: string;
  appliedSettings: UISchedulerSettings;
}

export interface UIOptimizationStats {
  executionTimeMs: number;
  objectiveValue: number;
  totalVariables: number;
  totalConstraints: number;
}

export interface UIFinancials {
  totalEnterpriseCost: number;
  totalIncentiveCost: number;
  totalOvertimeCost: number;
  regularPayCost: number;
}

export type UIValidationLevel = "ok" | "warning" | "critical" | "stale" | "unspecified";

export interface UIPatchConflict {
  patchId: string;
  employeeId: string;
  employeeName: string | null;
  fromShiftId: string | null;
  toShiftId: string | null;
  reason: string;
  latestShiftId: string | null;
}

export interface UIStagedPatch {
  patchId: string;
  employeeId: string;
  employeeName: string | null;
  fromShiftId: string | null;
  toShiftId: string | null;
  pinned: boolean;
  warnings: string[];
  validationLevel: UIValidationLevel;
  causesOvertime: boolean;
  totalCost: number;
  createdAt: string | null;
}

export type UIOptimizationRunStatus = "queued" | "running" | "completed" | "failed" | "unspecified";
export type UIOptimizationRunStage =
  | "unspecified"
  | "queued"
  | "snapshotting"
  | "indexing"
  | "building_model"
  | "solving"
  | "analyzing"
  | "publishing"
  | "completed"
  | "failed";

export interface UIOptimizationRun {
  runId: string;
  scheduleId: string;
  baseScheduleVersion: number;
  resultScheduleVersion: number | null;
  status: UIOptimizationRunStatus;
  stage: UIOptimizationRunStage;
  progressPercent: number;
  statusMessage: string;
  startedAt: string | null;
  completedAt: string | null;
  errorDetails: string | null;
  financials: UIFinancials | null;
  stats: UIOptimizationStats | null;
  summary: UIOptimizationSummary | null;
  stageTimings: StageTiming[];
}

export interface StageTiming {
  stage: UIOptimizationRunStage;
  durationMs: number;
}

export interface RunHistoryEntry {
  run: UIOptimizationRun;
  preSchedule: Record<string, UIDaySchedule>;
  postSchedule: Record<string, UIDaySchedule> | null;
  stagedPatches: UIStagedPatch[];
  completedAt: string;
}

export interface UIDraftState {
  baseScheduleVersion: number;
  patches: UIStagedPatch[];
  conflicts: UIPatchConflict[];
  hasPendingValidation: boolean;
}

export interface UINurse {
  id: string;
  name: string;
  role: string;
  shiftHours: number;
  schedulingRationale: string;
  isAgency: boolean;
}

export interface UIShift {
  shiftId: string;
  shiftName: "Morning" | "Afternoon" | "Night";
  unitId: string;
  unitName: string;
  patientCount: number;
  requiredHPRD: number;
  requiredHours: number;
  actualHours: number;
  isHPRDMet: boolean;
  nurses: UINurse[];
}

export interface UIDaySchedule {
  date: string;
  shifts: UIShift[];
}

export interface UISchedulePayload {
  scheduleId: string;
  scheduleVersion: number;
  facilityId: string;
  schedules: Map<string, UIDaySchedule>;
  latestOptimization: UIOptimizationSummary | null;
  optimizationStats?: UIOptimizationStats | null;
  optimizationFinancials?: UIFinancials | null;
  activeOptimizationRun?: UIOptimizationRun | null;
  updatedAt?: string | null;
}

export type ScheduleMap = Map<string, UIDaySchedule>;

export interface UICalendarDay {
  date: Date | null;
  dateString: string;
  dayOfMonth: number;
  isToday: boolean;
  isCurrentMonth: boolean;
  isSelectable: boolean;
  schedule: UIDaySchedule | null;
  dayHPRDPercentage: number;
  isPadding: boolean;
  coverage: number;
}
