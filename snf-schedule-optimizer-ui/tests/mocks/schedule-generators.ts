import { UIDaySchedule, UINurse, UIShift } from "@/types/scheduling";
import { SHIFT_NAMES, formatDateYYYYMMDD } from "@/lib/scheduling-logic";

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

const createShift = (
  shiftName: "Morning" | "Afternoon" | "Night",
  date: Date,
): UIShift => {
  const patientCount = 30 + Math.floor(Math.random() * 15);
  const requiredHPRD = 5.5;

  const requiredHours = patientCount * requiredHPRD;

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
  const isHPRDMet =
    actualHours >= requiredHours && (isWeekend ? Math.random() > 0.3 : true);

  return {
    shiftId: `${formatDateYYYYMMDD(date)}-${shiftName.toLowerCase()}`,
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

export function generateMockScheduleMap(
  startDate: Date,
  daysToGenerate: number = 14,
): Map<string, UIDaySchedule> {
  const map = new Map<string, UIDaySchedule>();

  const mutableDate = new Date(startDate);

  mutableDate.setHours(0, 0, 0, 0);

  for (let i = 0; i < daysToGenerate; i++) {
    const dateString = formatDateYYYYMMDD(mutableDate);

    const shifts: UIShift[] = SHIFT_NAMES.map((name) =>
      createShift(name, mutableDate),
    );

    map.set(dateString, {
      date: dateString,
      shifts: shifts,
    });

    mutableDate.setDate(mutableDate.getDate() + 1);
  }
  return map;
}

const createEmptyShift = (
  shiftName: "Morning" | "Afternoon" | "Night",
): UIShift => {
  const patientCount = 30 + Math.floor(Math.random() * 15);
  const requiredHPRD = 5.5;
  const requiredHours = patientCount * requiredHPRD;

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
    nurses: [],
  };
};

export function generateEmptyScheduleMap(
  startDate: Date,
  daysToGenerate: number = 14,
): Map<string, UIDaySchedule> {
  const map = new Map<string, UIDaySchedule>();
  const mutableDate = new Date(startDate);

  for (let i = 0; i < daysToGenerate; i++) {
    const dateString = formatDateYYYYMMDD(mutableDate);

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
