// Define domain types used across the UI. We intentionally declare our own
// lightweight interfaces here (instead of directly re-using the generated
// protobuf types) so the UI code can rely on consistent property casing and
// optional fields.

export interface UINurse {
    id: string;
    name: string;
    shiftHours: number;
    schedulingRationale: string;
}

export interface UIShift {
    // "Morning" | "Afternoon" | "Night"
    shiftName: 'Morning' | 'Afternoon' | 'Night';
    patientCount: number;
    // Note: UI logic uses `requiredHRPD` casing (not `requiredHrpd` from proto)
    requiredHPRD: number;
    requiredHours: number;
    actualHours: number;
    // UI uses `isHPRDMet` boolean flag
    isHPRDMet: boolean;
    nurses: UINurse[];
}

export interface UIDaySchedule {
    // YYYY-MM-DD
    date: string;
    shifts: UIShift[];
}

// Structure for the received schedules (Map from YYYY-MM-DD string to DaySchedule)
export type ScheduleMap = Map<string, UIDaySchedule>;

export interface UICalendarDay {
    date: Date | null;
    dateString: string; // YYYY-MM-DD
    dayOfMonth: number;
    isToday: boolean;
    isCurrentMonth: boolean;
    isSelectable: boolean;
    schedule: UIDaySchedule | null;
    dayHPRDPercentage: number;
    isPadding: boolean;
    coverage: number;
}