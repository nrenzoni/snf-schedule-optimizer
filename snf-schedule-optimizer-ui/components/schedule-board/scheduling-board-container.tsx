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
  const { effectiveScheduleMap, draftPatches, runStatus } = useSchedulingStore(
    useShallow((state) => ({
      effectiveScheduleMap: state.effectiveScheduleMap,
      draftPatches: state.draftState.patches,
      runStatus: state.activeRun?.status ?? null,
    })),
  );

  const { shifts, staffList, units, targetShiftIds } = useMemo(() => {
    const boardShifts: Shift[] = [];
    const staffById = new Map<string, Staff>();
    const unitsById = new Map<string, SimulatedUnit>();
    const targetShiftMap = new Map<string, string>();
    const patchByEmployeeAndShift = new Map<string, (typeof draftPatches)[number]>();

    for (const patch of draftPatches) {
      if (patch.toShiftId) {
        patchByEmployeeAndShift.set(`${patch.employeeId}:${patch.toShiftId}`, patch);
      }
    }

    for (const [dateStr, daySchedule] of effectiveScheduleMap.entries()) {
      for (const shift of daySchedule.shifts) {
        targetShiftMap.set(`${shift.unitId}:${dateStr}:${shiftNameToType(shift.shiftName)}`, shift.shiftId);
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

          const patch = patchByEmployeeAndShift.get(`${nurse.id}:${shift.shiftId}`);
          boardShifts.push({
            id: `${shift.shiftId}:${nurse.id}`,
            shiftId: shift.shiftId,
            staffId: nurse.id,
            employeeName: nurse.name,
            dateStr,
            unitId: shift.unitId,
            role,
            shiftType: shiftNameToType(shift.shiftName),
            isAgency: nurse.isAgency,
            isOvertime: nurse.shiftHours > 8,
            pinned: patch?.pinned ?? false,
            warnings: patch?.warnings ?? [],
            validationLevel: patch?.validationLevel,
            totalCost: patch?.totalCost,
          });
        }
      }
    }

    return {
      shifts: boardShifts,
      staffList: Array.from(staffById.values()),
      units: Array.from(unitsById.values()),
      targetShiftIds: targetShiftMap,
    };
  }, [draftPatches, effectiveScheduleMap]);

  return (
    <ScheduleBoard
      shifts={shifts}
      staffList={staffList}
      units={units}
      targetShiftIds={targetShiftIds}
      dragDisabled={runStatus === "queued" || runStatus === "running"}
    />
  );
}
