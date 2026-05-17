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
import { UIShift, UIDaySchedule, UIStagedPatch } from "@/types/scheduling";
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
    default:
      return "DAY";
  }
};

type EffectiveScheduleMap = Map<string, UIDaySchedule>;

function buildShifts(
  effectiveScheduleMap: EffectiveScheduleMap,
  draftPatches: UIStagedPatch[],
): { shifts: Shift[]; targetShiftIds: Map<string, string> } {
  const boardShifts: Shift[] = [];
  const targetShiftMap = new Map<string, string>();
  const staffById = new Map<string, Staff>();
  const patchByEmployeeAndShift = new Map<string, UIStagedPatch>();

  for (const patch of draftPatches) {
    if (patch.toShiftId) {
      patchByEmployeeAndShift.set(`${patch.employeeId}:${patch.toShiftId}`, patch);
    }
  }

  for (const [dateStr, daySchedule] of effectiveScheduleMap.entries()) {
    for (const shift of daySchedule.shifts) {
      targetShiftMap.set(
        `${shift.unitId}:${dateStr}:${shiftNameToType(shift.shiftName)}`,
        shift.shiftId,
      );

      for (const nurse of shift.nurses) {
        const role = roleToBoardRole(nurse.role);
        const rowId = `${shift.unitId}:${nurse.id}`;
        if (!staffById.has(rowId)) {
          staffById.set(rowId, {
            id: nurse.id,
            rowId,
            name: nurse.name,
            role,
            unitId: shift.unitId,
            fte: 1,
          });
        }

        const patch = patchByEmployeeAndShift.get(`${nurse.id}:${shift.shiftId}`);
        boardShifts.push({
          id: `${shift.shiftId}:${nurse.id}`,
          rowId,
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

  return { shifts: boardShifts, targetShiftIds: targetShiftMap };
}

function buildStaffMap(
  effectiveScheduleMap: EffectiveScheduleMap,
): Staff[] {
  const staffById = new Map<string, Staff>();

  for (const [, daySchedule] of effectiveScheduleMap.entries()) {
    for (const shift of daySchedule.shifts) {
      for (const nurse of shift.nurses) {
        const role = roleToBoardRole(nurse.role);
        const rowId = `${shift.unitId}:${nurse.id}`;
        if (!staffById.has(rowId)) {
          staffById.set(rowId, {
            id: nurse.id,
            rowId,
            name: nurse.name,
            role,
            unitId: shift.unitId,
            fte: 1,
          });
        }
      }
    }
  }

  return Array.from(staffById.values());
}

function buildUnitMap(
  effectiveScheduleMap: EffectiveScheduleMap,
): SimulatedUnit[] {
  const unitsById = new Map<string, SimulatedUnit>();

  for (const [, daySchedule] of effectiveScheduleMap.entries()) {
    for (const shift of daySchedule.shifts) {
      unitsById.set(shift.unitId, {
        id: shift.unitId,
        label: shift.unitName,
      });
    }
  }

  return Array.from(unitsById.values());
}

export default function ScheduleBoardContainer() {
  const { effectiveScheduleMap, draftPatches, runStatus } = useSchedulingStore(
    useShallow((state) => ({
      effectiveScheduleMap: state.effectiveScheduleMap,
      draftPatches: state.draftState.patches,
      runStatus: state.activeRun?.status ?? null,
    })),
  );

  const { shifts, staffList, units, targetShiftIds } = useMemo(() => {
    const { shifts: boardShifts, targetShiftIds: tgtMap } = buildShifts(
      effectiveScheduleMap,
      draftPatches,
    );
    const staffList = buildStaffMap(effectiveScheduleMap);
    const unitList = buildUnitMap(effectiveScheduleMap);

    return {
      shifts: boardShifts,
      staffList,
      units: unitList,
      targetShiftIds: tgtMap,
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
