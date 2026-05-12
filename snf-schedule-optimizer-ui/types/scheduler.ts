export type Shift = {
  id: string;
  staffId: string;
  dateStr: string;
  role: RoleKey;
  shiftType: ShiftTypeKey;
  // Metadata for "Budget" view
  isOvertime?: boolean;
  isAgency?: boolean;
};

export type Staff = {
  id: string;
  name: string;
  role: RoleKey;
  unitId: UnitKey; // Staff "Home" Unit
  fte: number; // 1.0 = full time
};

export type GroupMetric = {
  filledPct: number; // 0 to 1+
  label: string; // e.g. "0.65" or "$1.2k"
  status: "ok" | "warning" | "critical";
};

export type SimulatedUnit = {
  id: string;
  label: string;
};

export const UNITS = {
  U1: { id: "U1", label: "1st Floor - Rehab" },
  U2: { id: "U2", label: "2nd Floor - LTC" },
} as const;

// 1. Role Definitions (The "Vertical Groups")
export const ROLES = {
  RN: {
    label: "Registered Nurses",
    budgetGroup: "Nursing",
    baseRate: 45,
    targetHPRD: 0.75,
    dailyBudget: 2000,
  },
  LPN: {
    label: "Licensed Practical Nurses",
    budgetGroup: "Nursing",
    baseRate: 32,
    targetHPRD: 1.0,
    dailyBudget: 1500,
  },
  CNA: {
    label: "Certified Nursing Assistants",
    budgetGroup: "Nursing",
    baseRate: 20,
    targetHPRD: 2.4,
    dailyBudget: 1200,
  },
  THERAPIST: {
    label: "Physical Therapy",
    budgetGroup: "Therapy",
    baseRate: 55,
    targetHPRD: 0.1,
    dailyBudget: 500,
  },
} as const;

export const SHIFT_TYPES = {
  DAY: { id: "DAY", label: "D", hours: 8 },
  EVE: { id: "EVE", label: "E", hours: 8 },
  NIGHT: { id: "NIGHT", label: "N", hours: 8 },
} as const;

export type UnitKey = keyof typeof UNITS;
export type RoleKey = keyof typeof ROLES;
export type ShiftTypeKey = keyof typeof SHIFT_TYPES;
export type ViewMode = "ROLE" | "BUDGET";
export type ColorMode = "ROLE" | "BUDGET";
