"use client";

import React, { useMemo } from "react";
import ScheduleBoard from "@/components/schedule-board/schedule-board";
import {
  RoleKey,
  Shift,
  ShiftTypeKey,
  SimulatedUnit,
  Staff,
} from "@/types/scheduler";
import { UIShift } from "@/types/scheduling";
import { useSchedulingStore } from "@/store/schedulingStore";
import { useShallow } from "zustand/react/shallow";

const roleToBoardRole = (role: string): RoleKey => {
  const normalizedRole = role.toUpperCase();

  if (normalizedRole.includes("THERAP") || normalizedRole.includes(" PT")) {
    return "THERAPIST";
  }
  if (normalizedRole.includes("RN")) {
    return "RN";
  }
  if (normalizedRole.includes("LPN") || normalizedRole.includes("LVN")) {
    return "LPN";
  }
  return "CNA";
};

const shiftNameToType = (shiftName: UIShift["shiftName"]): ShiftTypeKey => {
  switch (shiftName) {
    case "Morning":
      return "DAY";
    case "Afternoon":
      return "EVE";
    case "Night":
      return "NIGHT";
  }
};

export default function ScheduleBoardContainer() {
  const { scheduleMap } = useSchedulingStore(
    useShallow((state) => ({
      scheduleMap: state.scheduleMap,
    })),
  );

  const { shifts, staffList, units } = useMemo(() => {
    const boardShifts: Shift[] = [];
    const staffById = new Map<string, Staff>();
    const unitsById = new Map<string, SimulatedUnit>();

    for (const [dateStr, daySchedule] of scheduleMap.entries()) {
      for (const shift of daySchedule.shifts) {
        unitsById.set(shift.unitId, {
          id: shift.unitId,
          label: shift.unitName,
        });

        for (const nurse of shift.nurses) {
          const role = roleToBoardRole(nurse.role);
          if (!staffById.has(nurse.id)) {
            staffById.set(nurse.id, {
              id: nurse.id,
              name: nurse.name,
              role,
              unitId: shift.unitId,
              fte: 1,
            });
          }

          boardShifts.push({
            id: `${shift.shiftId}:${nurse.id}`,
            staffId: nurse.id,
            dateStr,
            role,
            shiftType: shiftNameToType(shift.shiftName),
            isAgency: nurse.isAgency,
            isOvertime: nurse.shiftHours > 8,
          });
        }
      }
    }

    return {
      shifts: boardShifts,
      staffList: Array.from(staffById.values()),
      units: Array.from(unitsById.values()),
    };
  }, [scheduleMap]);

  return <ScheduleBoard initialShifts={shifts} staffList={staffList} units={units} />;
}
