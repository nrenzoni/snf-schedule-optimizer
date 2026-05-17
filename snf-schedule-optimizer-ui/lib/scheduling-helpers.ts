import { create } from "@bufbuild/protobuf";
import { match } from "ts-pattern";
import { StagedSchedulePatchSchema, ValidationLevel } from "@/gen/scheduling/v1/scheduling_pb";
import { ScheduleMap, UINurse, UIStagedPatch } from "@/types/scheduling";

const cloneMap = (map: ScheduleMap): ScheduleMap => new Map(map);

const removeEmployeeFromShift = (map: ScheduleMap, employeeId: string, shiftId: string | null) => {
  if (!shiftId) return;
  for (const [date, day] of map.entries()) {
    const shifts = day.shifts.map((shift) => {
      if (shift.shiftId !== shiftId) return shift;
      return {
        ...shift,
        nurses: shift.nurses.filter((nurse) => nurse.id !== employeeId),
      };
    });
    map.set(date, { ...day, shifts });
  }
};

const addEmployeeToShift = (
  map: ScheduleMap,
  employeeId: string,
  shiftId: string | null,
  employeeName: string | null,
  nurseLookup: Map<string, UINurse>,
) => {
  if (!shiftId) return;
  for (const [date, day] of map.entries()) {
    const shifts = day.shifts.map((shift) => {
      if (shift.shiftId !== shiftId) return shift;
      if (shift.nurses.some((nurse) => nurse.id === employeeId)) {
        return shift;
      }
      const sourceNurse = nurseLookup.get(employeeId);
      return {
        ...shift,
        nurses: [
          ...shift.nurses,
          sourceNurse ?? {
            id: employeeId,
            name: employeeName ?? "Manual Assignment",
            role: "",
            shiftHours: 8,
            schedulingRationale: "Pinned manual assignment",
            isAgency: false,
          },
        ],
      };
    });
    map.set(date, { ...day, shifts });
  }
};

export const applyPatchToMap = (serverScheduleMap: ScheduleMap, patches: UIStagedPatch[]): ScheduleMap => {
  const next = cloneMap(serverScheduleMap);
  const nurseLookup = new Map<string, UINurse>();
  for (const day of serverScheduleMap.values()) {
    for (const shift of day.shifts) {
      for (const nurse of shift.nurses) {
        if (!nurseLookup.has(nurse.id)) {
          nurseLookup.set(nurse.id, nurse);
        }
      }
    }
  }
  for (const patch of patches) {
    removeEmployeeFromShift(next, patch.employeeId, patch.fromShiftId);
    addEmployeeToShift(next, patch.employeeId, patch.toShiftId, patch.employeeName, nurseLookup);
  }
  return next;
};

export const toProtoPatch = (patch: UIStagedPatch) =>
  create(StagedSchedulePatchSchema, {
    patchId: patch.patchId,
    employeeId: patch.employeeId,
    employeeName: patch.employeeName ?? "",
    fromShiftId: patch.fromShiftId ?? "",
    toShiftId: patch.toShiftId ?? "",
    pinned: patch.pinned,
    warnings: patch.warnings,
    validationLevel: match(patch.validationLevel)
      .with("ok", () => ValidationLevel.VALIDATION_OK)
      .with("warning", () => ValidationLevel.VALIDATION_WARNING)
      .with("critical", () => ValidationLevel.VALIDATION_CRITICAL)
      .with("stale", () => ValidationLevel.VALIDATION_STALE)
      .with("unspecified", () => ValidationLevel.VALIDATION_LEVEL_UNSPECIFIED)
      .exhaustive(),
    totalCost: patch.totalCost,
    causesOvertime: patch.causesOvertime,
    createdAt: patch.createdAt ?? "",
  });

export const isRunActive = (status: string | null | undefined) =>
  match(status)
    .with("queued", "running", () => true)
    .otherwise(() => false);
