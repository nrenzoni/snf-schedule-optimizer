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
