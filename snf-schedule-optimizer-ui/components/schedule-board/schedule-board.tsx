"use client";

import React, { useId, useMemo, useState } from "react";
import {
  closestCenter,
  defaultDropAnimationSideEffects,
  DndContext,
  DragEndEvent,
  DragOverlay,
  Modifier,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { addDays, format, isSameDay, startOfWeek, subDays } from "date-fns";
import { cn, createClientUuid } from "@/lib/utils";
import {
  Activity,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  DollarSign,
  LayoutList,
  RotateCcw,
} from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  MoveValidationPreview,
  Shift,
  SHIFT_TYPES,
  ShiftTypeKey,
  SimulatedUnit,
  Staff,
  TimelineSlotData,
  ViewMode,
} from "@/types/scheduler";
import ShiftCard from "@/components/schedule-board/shift-card";
import UnitGroup from "@/components/schedule-board/unit-group";
import { useIsFetching } from "@tanstack/react-query";
import LoadingOverlay from "../ui/loading-overlay";
import { useSchedulingStore } from "@/store/schedulingStore";
import { useShallow } from "zustand/react/shallow";
import { parseAsString, useQueryState } from "nuqs";
import { formatDateYYYMMDD, TODAY_STRING } from "@/utils/scheduling-logic";
import { iconButtonVariants, segmentedButtonVariants } from "@/components/ui/styles";
import { create } from "@bufbuild/protobuf";
import { StagedSchedulePatchSchema } from "@/gen/scheduling/v1/scheduling_pb";
import { validateShiftMove } from "@/api/scheduling-client";
import { protoPatchConflictToUI, protoStagedPatchToUI } from "@/hooks/use-schedule-query";
import { useStagedScheduleActions } from "@/hooks/use-staged-schedule-actions";
import ThreeDAssemblyLoader from "@/components/three-d-assembly-loader";

export const STAFF_COL_WIDTH = "w-48 min-w-[12rem]";
export const CELL_WIDTH = "w-[72px] min-w-[72px]";
export const DATE_GROUP_WIDTH = "w-[216px] min-w-[216px]";

const restrictToHorizontalAxis: Modifier = ({ transform }) => ({
  ...transform,
  y: 0,
});

const VISIBLE_DAY_COUNT = 6;

interface ScheduleBoardProps {
  shifts: Shift[];
  staffList: Staff[];
  units: SimulatedUnit[];
  targetShiftIds: Map<string, string>;
  dragDisabled: boolean;
}

export default function ScheduleBoard({
  shifts,
  staffList,
  units,
  targetShiftIds,
  dragDisabled,
}: ScheduleBoardProps) {
  const dndContextId = useId();
  const isFetching = useIsFetching();
  const {
    selectedFacility,
    scheduleId,
    scheduleVersion,
    draftState,
    scheduleCount,
    activeRun,
    appendDraftPatch,
    clearDraft,
    setDraftConflicts,
    setHasPendingValidation,
  } = useSchedulingStore(
    useShallow((state) => ({
      selectedFacility: state.selectedFacility,
      scheduleId: state.scheduleId,
      scheduleVersion: state.scheduleVersion,
      draftState: state.draftState,
      scheduleCount: state.effectiveScheduleMap.size,
      activeRun: state.activeRun,
      appendDraftPatch: state.appendDraftPatch,
      clearDraft: state.clearDraft,
      setDraftConflicts: state.setDraftConflicts,
      setHasPendingValidation: state.setHasPendingValidation,
    })),
  );
  const { stageValidatedPatch } = useStagedScheduleActions();
  const [anchorDateStr, setAnchorDateStr] = useQueryState(
    "anchor",
    parseAsString.withDefault(TODAY_STRING),
  );

  const [viewMode, setViewMode] = useState<ViewMode>("ROLE");
  const [groupingMode, setGroupingMode] = useState<"ROLE" | "BUDGET">("ROLE");
  const [activeShift, setActiveShift] = useState<Shift | null>(null);
  const [pendingSlotId, setPendingSlotId] = useState<string | null>(null);
  const [validationPreview, setValidationPreview] =
    useState<MoveValidationPreview | null>(null);

  const [expandedUnits, setExpandedUnits] = useState<Record<string, boolean>>({});
  const [expandedRoles, setExpandedRoles] = useState<Record<string, boolean>>({
    "U1-RN": true,
  });

  const unitGroups = useMemo(() => {
    return units.map((unit) => ({
      unit,
      staff: staffList.filter((s) => s.unitId === unit.id),
    }));
  }, [staffList, units]);

  const anchorDate = useMemo(() => new Date(anchorDateStr), [anchorDateStr]);
  const visibleStartDate = useMemo(() => subDays(anchorDate, 2), [anchorDate]);
  const visibleDates = useMemo(
    () => Array.from({ length: VISIBLE_DAY_COUNT }, (_, index) => addDays(visibleStartDate, index)),
    [visibleStartDate],
  );

  const resolveTargetShiftId = (unitId: string, dateStr: string, shiftKey: ShiftTypeKey) => {
    return targetShiftIds.get(`${unitId}:${dateStr}:${shiftKey}`) ?? null;
  };

  const pageSchedule = (dayDelta: number) => {
    setAnchorDateStr(formatDateYYYMMDD(addDays(anchorDate, dayDelta)));
  };

  const handleCollapseAll = () => {
    setExpandedUnits({});
    setExpandedRoles({});
  };

  const handleExpandAll = () => {
    const allUnits = Object.fromEntries(units.map((unit) => [unit.id, true]));
    setExpandedUnits(allUnits);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setPendingSlotId(null);

    if (!over) {
      setValidationPreview(null);
      return;
    }

    const activeData = active.data.current?.shift as Shift | undefined;
    const overData = over.data.current as TimelineSlotData | undefined;

    if (
      !activeData ||
      !overData ||
      !selectedFacility ||
      !scheduleId ||
      !overData.shiftId ||
      dragDisabled
    ) {
      setValidationPreview(null);
      return;
    }

    if (activeData.shiftId === overData.shiftId) {
      setValidationPreview(null);
      return;
    }

    try {
      setHasPendingValidation(true);
      const slotId = String(over.id);
      setPendingSlotId(slotId);

      const payPeriodStart = startOfWeek(new Date(activeData.dateStr), { weekStartsOn: 0 });
      const response = await validateShiftMove({
        orgId: selectedFacility.orgId,
        facilityId: selectedFacility.facilityId,
        scheduleId,
        employeeId: activeData.staffId,
        fromShiftId: activeData.shiftId,
        toShiftId: overData.shiftId,
        payPeriodStartTs: BigInt(Math.floor(payPeriodStart.getTime() / 1000)),
        scheduleVersion,
        stagedPatches: draftState.patches.map((patch) =>
          create(StagedSchedulePatchSchema, {
            patchId: patch.patchId,
            employeeId: patch.employeeId,
            employeeName: patch.employeeName ?? "",
            fromShiftId: patch.fromShiftId ?? "",
            toShiftId: patch.toShiftId ?? "",
            pinned: patch.pinned,
            warnings: patch.warnings,
            causesOvertime: patch.causesOvertime,
            totalCost: patch.totalCost,
            createdAt: patch.createdAt ?? "",
          }),
        ),
        patchId: createClientUuid(),
      });

      const preview: MoveValidationPreview = {
        validationLevel: response.isStale
          ? "stale"
          : response.patch
            ? protoStagedPatchToUI(response.patch).validationLevel
            : response.isValid
              ? "ok"
              : "critical",
        warnings: response.warnings,
        causesOvertime: response.patch?.causesOvertime ?? false,
        totalCost: response.totalCost,
        isValid: response.isValid,
        errorDetails: response.errorDetails || undefined,
      };
      setValidationPreview(preview);

      if (!response.isSuccess) {
        toast.error("Move validation failed", {
          description: response.errorDetails || "The backend could not validate this move.",
        });
        return;
      }

      if (response.conflicts.length > 0) {
        setDraftConflicts(response.conflicts.map(protoPatchConflictToUI));
      }

      if (response.isStale) {
        toast.error("Schedule changed on the server", {
          description: "Refresh before applying more staged changes.",
        });
        return;
      }

      if (!response.isValid || !response.patch) {
        toast.error("Move blocked", {
          description: response.errorDetails || response.warnings.join(" ") || "This move is not allowed.",
        });
        return;
      }

      appendDraftPatch(protoStagedPatchToUI(response.patch));
      toast.success("Pinned change staged", {
        description:
          response.warnings.join(" ") ||
          (response.patch.causesOvertime
            ? "Move staged with overtime warning."
            : "Validated move staged locally until optimization."),
      });
    } catch (error) {
      toast.error("Move validation failed", {
        description: error instanceof Error ? error.message : "Unexpected scheduling error",
      });
    } finally {
      setPendingSlotId(null);
      setHasPendingValidation(false);
    }
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  return (
    <DndContext
      id={dndContextId}
      sensors={sensors}
      collisionDetection={closestCenter}
      modifiers={[restrictToHorizontalAxis]}
      onDragStart={(e) => setActiveShift(e.active.data.current?.shift)}
      onDragEnd={(event) => void handleDragEnd(event)}
      onDragCancel={() => {
        setPendingSlotId(null);
        setValidationPreview(null);
      }}
    >
      <div className="app-card relative flex h-full min-h-0 flex-col overflow-hidden xl:min-h-0">
        <LoadingOverlay isVisible={isFetching > 0 && scheduleCount > 0} />

        <div className="z-50 flex items-center justify-between border-b border-border bg-card px-4 py-3">
          <div className="flex items-center gap-3">
            <h2 className="flex items-center gap-2 font-semibold text-foreground">
              <LayoutList size={18} className="text-primary" /> Master Schedule
            </h2>
            <div className="app-segmented flex items-center gap-1 p-1">
              <button
                type="button"
                onClick={() => pageSchedule(-VISIBLE_DAY_COUNT)}
                className={iconButtonVariants({ tone: "default" })}
                aria-label="Show previous 6 days"
              >
                <ChevronLeft size={16} />
              </button>
              <span className="px-2 text-xs font-medium text-muted-foreground">
                {format(visibleDates[0], "MMM d")} - {format(visibleDates[VISIBLE_DAY_COUNT - 1], "MMM d")}
              </span>
              <button
                type="button"
                onClick={() => pageSchedule(VISIBLE_DAY_COUNT)}
                className={iconButtonVariants({ tone: "default" })}
                aria-label="Show next 6 days"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={clearDraft}
              disabled={draftState.patches.length === 0}
              className={iconButtonVariants({ tone: "soft", disabled: draftState.patches.length === 0 })}
              aria-label="Revert staged changes"
            >
              <RotateCcw size={14} />
            </button>
            <div className="app-segmented flex items-center text-xs font-bold">
              <span className="px-2 text-slate-500">Sub-Group:</span>
              <button
                onClick={() => setGroupingMode("ROLE")}
                className={segmentedButtonVariants({ size: "sm", active: groupingMode === "ROLE" })}
              >
                Role
              </button>
              <button
                onClick={() => setGroupingMode("BUDGET")}
                className={segmentedButtonVariants({ size: "sm", active: groupingMode === "BUDGET" })}
              >
                Budget
              </button>
            </div>
            <div className="app-segmented flex items-center text-xs font-bold">
              <span className="px-2 text-slate-500">Metric:</span>
              <button
                onClick={() => setViewMode("ROLE")}
                className={segmentedButtonVariants({ size: "sm", active: viewMode === "ROLE" })}
              >
                <Activity size={12} /> HPRD
              </button>
              <button
                onClick={() => setViewMode("BUDGET")}
                className={segmentedButtonVariants({ size: "sm", active: viewMode === "BUDGET" })}
              >
                <DollarSign size={12} /> Cost
              </button>
            </div>
          </div>
        </div>

        <div className="relative flex-1 overflow-auto bg-background xl:min-h-0">
          <ThreeDAssemblyLoader
            isLoading={dragDisabled}
            mode="inline"
            progressPercent={activeRun?.progressPercent}
            message={activeRun?.statusMessage || undefined}
          />

          <div className="relative z-10 min-w-max p-4 pb-20">
            <div className="sticky top-0 z-40 mb-2 flex rounded-lg border border-border bg-card shadow-none">
              <div
                className={cn(
                  STAFF_COL_WIDTH,
                  "sticky left-0 z-50 flex items-center justify-between rounded-l-lg border-r border-border bg-card px-3 text-xs font-medium text-muted-foreground",
                )}
              >
                <div className="flex min-w-0 flex-col gap-1 py-2">
                  <span className="uppercase tracking-widest">Unit / Staff</span>
                  <span className="hidden text-[10px] font-medium tracking-normal text-slate-500 md:inline">
                    {units.length} units
                  </span>
                </div>
                <div className="hidden xl:flex items-center gap-1">
                  <button
                    onClick={handleCollapseAll}
                    className={iconButtonVariants({ tone: "soft" })}
                    aria-label="Collapse all groups"
                  >
                    <ChevronUp size={14} />
                  </button>
                  <button
                    onClick={handleExpandAll}
                    className={iconButtonVariants({ tone: "soft" })}
                    aria-label="Expand all groups"
                  >
                    <ChevronDown size={14} />
                  </button>
                </div>
              </div>
              {visibleDates.map((date, i) => {
                const isToday = isSameDay(date, new Date());
                return (
                  <div key={i} className={cn(DATE_GROUP_WIDTH, "border-r border-border last:border-0")}>
                    <div className="flex flex-col">
                      <div
                        className={cn(
                          "w-full border-b border-border py-1.5 text-center text-xs font-medium",
                          isToday ? "bg-primary text-primary-foreground" : "bg-background text-foreground",
                        )}
                      >
                        {format(date, "EEE, MMM d")}
                      </div>
                      <div className="flex">
                        {Object.values(SHIFT_TYPES).map((shift) => (
                          <div
                            key={shift.id}
                            className={cn(
                              CELL_WIDTH,
                              "border-r border-border py-1 text-center text-[10px] font-medium text-muted-foreground last:border-r-0",
                              isToday ? "bg-accent" : "bg-card",
                            )}
                          >
                            {shift.label}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <motion.div
              key={`${groupingMode}-${viewMode}`}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
            >
              {unitGroups.map((group) => (
                <UnitGroup
                  key={group.unit.id}
                  unit={group.unit}
                  staffMembers={group.staff}
                  shifts={shifts}
                  dates={visibleDates}
                  viewMode={viewMode}
                  groupingMode={groupingMode}
                  isExpanded={expandedUnits[group.unit.id] ?? true}
                  onToggle={() =>
                    setExpandedUnits((prev) => ({
                      ...prev,
                      [group.unit.id]: !prev[group.unit.id],
                    }))
                  }
                  roleState={expandedRoles}
                  toggleRole={(key: string) => setExpandedRoles((prev) => ({ ...prev, [key]: !prev[key] }))}
                  pendingSlotId={pendingSlotId}
                  validationPreview={validationPreview}
                  dragDisabled={dragDisabled}
                  resolveTargetShiftId={resolveTargetShiftId}
                  onDeleteShift={async (shift) => {
                    return stageValidatedPatch({
                      employeeId: shift.staffId,
                      employeeName: shift.employeeName,
                      fromShiftId: shift.shiftId,
                      toShiftId: null,
                      payPeriodStart: startOfWeek(new Date(shift.dateStr), { weekStartsOn: 0 }),
                      successTitle: "Shift removal staged",
                      successDescription:
                        "Assignment removal will be applied with the next optimization run.",
                    });
                  }}
                />
              ))}
            </motion.div>
          </div>
        </div>
      </div>
      <DragOverlay
        dropAnimation={{
          sideEffects: defaultDropAnimationSideEffects({
            styles: { active: { opacity: "0.5" } },
          }),
        }}
      >
        {activeShift ? <ShiftCard shift={activeShift} mode={viewMode} isOverlay /> : null}
      </DragOverlay>
    </DndContext>
  );
}
