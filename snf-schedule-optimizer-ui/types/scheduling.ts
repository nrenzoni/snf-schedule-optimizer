export interface Nurse {
    id: string;
    name: string;
    shiftHours: number;
    schedulingRationale: string;
}

export interface Shift {
    shiftName: 'Morning' | 'Afternoon' | 'Night';
    patientCount: number;
    requiredHRPD: number;
    requiredHours: number;
    actualHours: number;
    isHRPDMet: boolean;
    nurses: Nurse[];
}

export interface DaySchedule {
    date: string; // YYYY-MM-DD
    shifts: Shift[];
}

export interface CalendarDay {
    date: Date;
    dateString: string; // YYYY-MM-DD
    dayOfMonth: number;
    isToday: boolean;
    isCurrentMonth: boolean;
    isSelectable: boolean;
    schedule: DaySchedule | null;
    isDayHRPDMet: boolean;
    dayHRPDPercentage: number;
}