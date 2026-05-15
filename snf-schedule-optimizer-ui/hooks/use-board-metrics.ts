"use client";

import { useMemo } from "react";
import { format } from "date-fns";
import {
  GroupMetric,
  Shift,
  SHIFT_TYPES,
  ShiftTypeKey,
  SimulatedUnit,
  Staff,
  ViewMode,
} from "@/types/scheduler";
import { calculateCellMetric } from "@/components/schedule-board/utils";

export function useBoardMetrics(
  shifts: Shift[],
  units: SimulatedUnit[],
  staffByUnit: Map<string, Staff[]>,
  dates: Date[],
  viewMode: ViewMode,
  groupingMode: "ROLE" | "BUDGET",
): Map<string, GroupMetric> {
  return useMemo(() => {
    const metrics = new Map<string, GroupMetric>();
    const shiftKeys = Object.keys(SHIFT_TYPES) as ShiftTypeKey[];

    for (const unit of units) {
      const unitStaff = staffByUnit.get(unit.id) ?? [];

      const roleGroups = new Map<string, Staff[]>();
      for (const s of unitStaff) {
        const list = roleGroups.get(s.role) ?? [];
        list.push(s);
        roleGroups.set(s.role, list);
      }

      for (const date of dates) {
        const dateStr = format(date, "yyyy-MM-dd");

        for (const shiftKey of shiftKeys) {
          const unitKey = `${unit.id}::${dateStr}::${shiftKey}`;
          metrics.set(unitKey, calculateCellMetric(
            shifts,
            { unitId: unit.id },
            viewMode,
            groupingMode,
            unitStaff,
            dateStr,
            shiftKey,
          ));

          for (const [groupId, groupStaff] of roleGroups) {
            const roleKey = `${unit.id}:${groupId}::${dateStr}::${shiftKey}`;
            metrics.set(roleKey, calculateCellMetric(
              shifts,
              { unitId: unit.id, groupId },
              viewMode,
              groupingMode,
              groupStaff,
              dateStr,
              shiftKey,
            ));
          }
        }
      }
    }

    return metrics;
  }, [shifts, units, staffByUnit, dates, viewMode, groupingMode]);
}
