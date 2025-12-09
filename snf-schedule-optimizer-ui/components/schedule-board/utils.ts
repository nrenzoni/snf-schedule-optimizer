import {
  GroupMetric,
  ROLES,
  Shift,
  SHIFT_TYPES,
  ShiftTypeKey,
  Staff,
  ViewMode,
} from "@/types/scheduler";

export const calculateCellMetric = (
  shifts: Shift[],
  scope: { unitId: string; groupId?: string }, // Scope can be just Unit, or Unit+Role
  viewMode: ViewMode,
  groupingMode: "ROLE" | "BUDGET",
  staffListInScope: Staff[], // Pre-filtered list of staff in this scope
  dateStr: string,
  shiftType: ShiftTypeKey,
): GroupMetric => {
  // 1. Filter Shifts: Must match Date, Shift, AND match a staff member in this scope
  const staffIds = new Set(staffListInScope.map((s) => s.id));
  const cellShifts = shifts.filter(
    (s) =>
      s.dateStr === dateStr &&
      s.shiftType === shiftType &&
      staffIds.has(s.staffId),
  );

  if (viewMode === "ROLE") {
    // HPRD Logic
    const RESIDENT_COUNT = 40; // Approx residents per unit
    const totalHours = cellShifts.reduce(
      (acc, s) => acc + SHIFT_TYPES[s.shiftType].hours,
      0,
    );
    const actualHPRD = totalHours / RESIDENT_COUNT;

    // Target Logic: Sum targets of all roles present in this scope
    // If scope is Unit, it sums RN+LPN+CNA targets. If scope is Role, just that role.
    const uniqueRoles = Array.from(
      new Set(staffListInScope.map((s) => s.role)),
    );
    const targetHPRD = uniqueRoles.reduce(
      (sum, r) => sum + ROLES[r].targetHPRD,
      0,
    );

    const shiftTarget = targetHPRD / 3;
    const pct = shiftTarget > 0 ? actualHPRD / shiftTarget : 0;

    return {
      filledPct: pct,
      label: actualHPRD.toFixed(2),
      status: pct < 0.9 ? "critical" : pct > 1.1 ? "warning" : "ok",
    };
  } else {
    // Budget Logic
    const totalCost = cellShifts.reduce((acc, s) => {
      const rate = ROLES[s.role].baseRate;
      const hours = SHIFT_TYPES[s.shiftType].hours;
      const multiplier = s.isAgency ? 2.0 : s.isOvertime ? 1.5 : 1.0;
      return acc + rate * hours * multiplier;
    }, 0);

    // Mock Budget: $500 per shift per staff member roughly
    const LIMIT = staffListInScope.length * 150;
    const pct = LIMIT > 0 ? totalCost / LIMIT : 0;

    return {
      filledPct: pct,
      label: `$${(totalCost / 1000).toFixed(1)}k`,
      status: pct > 1.1 ? "critical" : pct > 0.9 ? "warning" : "ok",
    };
  }
};
