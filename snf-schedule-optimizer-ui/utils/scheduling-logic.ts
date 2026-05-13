import { UIDaySchedule, UINurse, UIShift } from "@/types/scheduling";

export const SHIFT_NAMES: ("Morning" | "Afternoon" | "Night")[] = [
  "Morning",
  "Afternoon",
  "Night",
];

export const getStartOfWeek = (date: Date): Date => {
  const day = date.getDay(); // 0 for Sunday, 1 for Monday, etc.
  const diff = day; // Days to subtract to get to Sunday (the start of the week)
  const startOfWeek = new Date(date);
  startOfWeek.setDate(date.getDate() - diff);
  startOfWeek.setHours(0, 0, 0, 0);
  return startOfWeek;
};

// Helper to get the start of the month (1st day)
export const getStartOfMonth = (date: Date): Date => {
  return new Date(date.getFullYear(), date.getMonth(), 1);
};

// Helper to format date to YYYY-MM-DD
export const formatDateYYYMMDD = (date: Date): string => {
  const d = new Date(date);
  const month = (d.getMonth() + 1).toString().padStart(2, "0");
  const day = d.getDate().toString().padStart(2, "0");
  const year = d.getFullYear();
  return [year, month, day].join("-");
};

// Calculate the end date for the 14-day window (today + 13 days)
export const getWindowEnd = (today: Date) => {
  const windowEnd = new Date(today);
  windowEnd.setDate(today.getDate() + 13);
  windowEnd.setHours(23, 59, 59, 999);
  return windowEnd;
};

const cleanToday = new Date();
cleanToday.setHours(0, 0, 0, 0);
export const TODAY = cleanToday;
export const TODAY_STRING = formatDateYYYMMDD(TODAY);
export const FOURTEEN_DAYS_AHEAD = getWindowEnd(TODAY);

// Helper function to create mock nurses for a specific shift
const createMockNurses = (
  shiftName: string,
  baseCount: number,
  variance: number,
): UINurse[] => {
  const nurses: UINurse[] = [];
  const count =
    baseCount +
    Math.floor(Math.random() * variance * (Math.random() > 0.5 ? 1 : -1));
  for (let i = 1; i <= Math.max(0, count); i++) {
    const id = `${shiftName.charAt(0)}${i}`;
    const name = `${shiftName} N ${String.fromCharCode(65 + i)}`;
    const hours = shiftName === "Night" ? 12 : 8;
    const priority = 90 - i * 5;
    const rationale = `System priority score ${priority}. Preferred due to shift bonus and no PTO request.`;
    nurses.push({
      id,
      name,
      role: "CNA",
      shiftHours: hours,
      schedulingRationale: rationale,
      isAgency: false,
    });
  }
  return nurses;
};

// Creates a single Shift object for a specific time period
const createShift = (
  shiftName: "Morning" | "Afternoon" | "Night",
  date: Date,
): UIShift => {
  const patientCount = 30 + Math.floor(Math.random() * 15);
  const requiredHPRD = 5.5;
  const shiftHours = shiftName === "Night" ? 12 : 8;

  const requiredHours = (patientCount / shiftHours) * requiredHPRD;

  const dayOfWeek = date.getDay();
  let baseNurses: number;

  if (shiftName === "Morning")
    baseNurses = dayOfWeek === 0 || dayOfWeek === 6 ? 3 : 5;
  else if (shiftName === "Afternoon")
    baseNurses = dayOfWeek === 0 || dayOfWeek === 6 ? 2 : 4;
  else baseNurses = 2;

  const nurses = createMockNurses(shiftName, baseNurses, 1);
  const actualHours = nurses.reduce((sum, nurse) => sum + nurse.shiftHours, 0);

  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
  // Add a bias to fail HPRD on weekends randomly for demonstration
  const isHPRDMet =
    actualHours >= requiredHours && (isWeekend ? Math.random() > 0.3 : true);

  return {
    shiftId: `${formatDateYYYMMDD(date)}-${shiftName.toLowerCase()}`,
    shiftName,
    unitId: "unit-mock",
    unitName: "Mock Unit",
    patientCount,
    requiredHPRD: requiredHPRD,
    requiredHours,
    actualHours,
    isHPRDMet,
    nurses,
  };
};

// production hook to fetch real schedules from backend
export function generateMockScheduleMap(
  startDate: Date,
  daysToGenerate: number = 14,
): Map<string, UIDaySchedule> {
  const map = new Map<string, UIDaySchedule>();

  // 1. Create a MUTABLE date object to track the current day of the iteration.
  // This is the key fix: use a single date object and advance it by one day in each loop.
  const mutableDate = new Date(startDate);

  // Ensure the date is cleaned to midnight, just like the input date should be.
  mutableDate.setHours(0, 0, 0, 0);

  for (let i = 0; i < daysToGenerate; i++) {
    // We are using 'mutableDate' as the current date for this iteration.

    const dateString = formatDateYYYMMDD(mutableDate);

    // Generate shifts using the helper function
    const shifts: UIShift[] = SHIFT_NAMES.map((name) =>
      createShift(name, mutableDate),
    );

    map.set(dateString, {
      date: dateString,
      shifts: shifts,
    });

    // 2. Advance the date by one day for the NEXT iteration.
    mutableDate.setDate(mutableDate.getDate() + 1);
  }
  return map;
}

// Helper to create an empty, unassigned shift for a specific date
const createEmptyShift = (
  shiftName: "Morning" | "Afternoon" | "Night",
): UIShift => {
  const patientCount = 30 + Math.floor(Math.random() * 15);
  const requiredHPRD = 5.5;
  const shiftHours = shiftName === "Night" ? 12 : 8;
  const requiredHours = (patientCount / shiftHours) * requiredHPRD;

  // Key difference: actualHours is 0, nurses is empty.
  return {
    shiftId: `empty-${shiftName.toLowerCase()}`,
    shiftName,
    unitId: "unit-mock",
    unitName: "Mock Unit",
    patientCount,
    requiredHPRD: requiredHPRD,
    requiredHours: requiredHours,
    actualHours: 0,
    isHPRDMet: false,
    nurses: [], // No nurses assigned
  };
};

// New mock generator for the pre-optimization state
export function generateEmptyScheduleMap(
  startDate: Date,
  daysToGenerate: number = 14,
): Map<string, UIDaySchedule> {
  const map = new Map<string, UIDaySchedule>();
  const mutableDate = new Date(startDate);

  for (let i = 0; i < daysToGenerate; i++) {
    const dateString = formatDateYYYMMDD(mutableDate);

    const shifts: UIShift[] = SHIFT_NAMES.map((name) =>
      createEmptyShift(name),
    );

    map.set(dateString, {
      date: dateString,
      shifts: shifts,
    });
    mutableDate.setDate(mutableDate.getDate() + 1);
  }
  return map;
}
