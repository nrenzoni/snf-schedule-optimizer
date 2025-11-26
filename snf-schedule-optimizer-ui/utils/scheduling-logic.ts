import {Nurse, Shift, DaySchedule} from '@/types/scheduling';

export const SHIFT_NAMES: ('Morning' | 'Afternoon' | 'Night')[] = ['Morning', 'Afternoon', 'Night'];
export const TODAY = new Date();

// Helper to get the start of the month (1st day)
export const getStartOfMonth = (date: Date): Date => {
    return new Date(date.getFullYear(), date.getMonth(), 1);
};

// Helper to format date to YYYY-MM-DD
export const formatDate = (date: Date): string => {
    const d = new Date(date);
    const month = (d.getMonth() + 1).toString().padStart(2, '0');
    const day = d.getDate().toString().padStart(2, '0');
    const year = d.getFullYear();
    return [year, month, day].join('-');
};

export const TODAY_STRING = formatDate(TODAY);

// Calculate the end date for the 14-day window (today + 13 days)
export const getWindowEnd = (today: Date) => {
    const windowEnd = new Date(today);
    windowEnd.setDate(today.getDate() + 13);
    windowEnd.setHours(23, 59, 59, 999);
    return windowEnd;
};
export const FOURTEEN_DAYS_AHEAD = getWindowEnd(TODAY);

// Helper function to create mock nurses for a specific shift
const createMockNurses = (shiftName: string, baseCount: number, variance: number): Nurse[] => {
    const nurses: Nurse[] = [];
    const count = baseCount + Math.floor(Math.random() * variance * (Math.random() > 0.5 ? 1 : -1));
    for (let i = 1; i <= Math.max(0, count); i++) {
        const id = `${shiftName.charAt(0)}${i}`;
        const name = `${shiftName} N ${String.fromCharCode(65 + i)}`;
        const hours = shiftName === 'Night' ? 12 : 8;
        const priority = 90 - i * 5;
        const rationale = `System priority score ${priority}. Preferred due to shift bonus and no PTO request.`;
        nurses.push({id, name, shiftHours: hours, schedulingRationale: rationale});
    }
    return nurses;
};

// Creates a single Shift object for a specific time period
const createShift = (shiftName: 'Morning' | 'Afternoon' | 'Night', date: Date): Shift => {
    const patientCount = 30 + Math.floor(Math.random() * 15);
    const requiredHRPD = 5.5;
    const shiftHours = (shiftName === 'Night' ? 12 : 8);

    const requiredHours = (patientCount / shiftHours) * requiredHRPD;

    const dayOfWeek = date.getDay();
    let baseNurses = 3;

    if (shiftName === 'Morning') baseNurses = (dayOfWeek === 0 || dayOfWeek === 6) ? 3 : 5;
    else if (shiftName === 'Afternoon') baseNurses = (dayOfWeek === 0 || dayOfWeek === 6) ? 2 : 4;
    else baseNurses = 2;

    const nurses = createMockNurses(shiftName, baseNurses, 1);
    const actualHours = nurses.reduce((sum, nurse) => sum + nurse.shiftHours, 0);

    const isWeekend = (dayOfWeek === 0 || dayOfWeek === 6);
    // Add a bias to fail HRPD on weekends randomly for demonstration
    const isHRPDMet = actualHours >= requiredHours && (isWeekend ? Math.random() > 0.3 : true);

    return {
        shiftName,
        patientCount,
        requiredHRPD,
        requiredHours,
        actualHours,
        isHRPDMet,
        nurses,
    };
};

/**
 * Generates a mock schedule map for the entire month of the given date.
 */
export const generateMockScheduleMap = (monthDate: Date): Map<string, DaySchedule> => {
    const map = new Map<string, DaySchedule>();
    const year = monthDate.getFullYear();
    const month = monthDate.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    for (let i = 1; i <= daysInMonth; i++) {
        const date = new Date(year, month, i);
        const dateString = formatDate(date);

        const shifts: Shift[] = SHIFT_NAMES.map(name => createShift(name, date));

        map.set(dateString, {
            date: dateString,
            shifts: shifts,
        });
    }
    return map;
};