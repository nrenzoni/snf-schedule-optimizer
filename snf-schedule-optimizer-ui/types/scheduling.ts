// Define domain types used across the UI. We intentionally declare our own
// lightweight interfaces here (instead of directly re-using the generated
// protobuf types) so the UI code can rely on consistent property casing and
// optional fields.

export interface Nurse {
    id: string;
    name: string;
    shiftHours: number;
    schedulingRationale: string;
}

export interface Shift {
    // "Morning" | "Afternoon" | "Night"
    shiftName: 'Morning' | 'Afternoon' | 'Night';
    patientCount: number;
    // Note: UI logic uses `requiredHRPD` casing (not `requiredHrpd` from proto)
    requiredHPRD: number;
    requiredHours: number;
    actualHours: number;
    // UI uses `isHPRDMet` boolean flag
    isHPRDMet: boolean;
    nurses: Nurse[];
}

export interface DaySchedule {
    // YYYY-MM-DD
    date: string;
    shifts: Shift[];
}

export interface CalendarDay {
    date: Date | null;
    dateString: string; // YYYY-MM-DD
    dayOfMonth: number;
    isToday: boolean;
    isCurrentMonth: boolean;
    isSelectable: boolean;
    schedule: DaySchedule | null;
    isDayHPRDMet: boolean;
    dayHPRDPercentage: number;
    isPadding: boolean;
    coverage: number;
}