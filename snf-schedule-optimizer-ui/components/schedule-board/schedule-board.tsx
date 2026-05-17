"use client";

import React, { useId, useMemo, useState } from "react";
import {
  closestCenter,
  defaultDropAnimationSideEffects,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { restrictToHorizontalAxis } from "@dnd-kit/modifiers";
import { addDays, format, isSameDay, startOfWeek, subDays } from "date-fns";
import { cn } from "@/lib/utils";
import {
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { motion } from "framer-motion";
import {
  Shift,
  SHIFT_TYPES,
  ShiftTypeKey,
  SimulatedUnit,
  Staff,
  ViewMode,
} from "@/types/scheduler";
import ShiftCard from "@/components/schedule-board/shift-card";
import UnitGroup from "@/components/schedule-board/unit-group";
import { useIsFetching } from "@tanstack/react-query";
import LoadingOverlay from "../ui/loading-overlay";
import { useSchedulingStore } from "@/store/schedulingStore";
import { useShallow } from "zustand/react/shallow";
import { parseAsString, useQueryState } from "nuqs";
import { formatDateYYYYMMDD, getTodayString } from "@/lib/scheduling-logic";
import { iconButtonVariants } from "@/components/ui/styles";
import { useDragValidation } from "@/hooks/use-drag-validation";
import { useStagedScheduleActions } from "@/hooks/use-staged-schedule-actions";
import BoardHeader from "@/components/schedule-board/board-header";
import { useBoardMetrics } from "@/hooks/use-board-metrics";
import dynamic from "next/dynamic";

const ThreeDAssemblyLoader = dynamic(
  () => import("@/components/three-d-assembly-loader"),
  { ssr: false },
);

export const STAFF_COL_WIDTH = "w-48 min-w-[12rem]";
export const CELL_WIDTH = "w-[72px] min-w-[72px]";
export const DATE_GROUP_WIDTH = "w-[216px] min-w-[216px]";

const VISIBLE_DAY_COUNT = 6;

interface ScheduleBoardProps {
  shifts: Shift[];
  staffList: Staff[];
  units: SimulatedUnit[];
  targetShiftIds: Map<string, string>;
  dragDisabled: boolean;
}

function useBoardExpansion(units: SimulatedUnit[]) {
  const [expandedUnits, setExpandedUnits] = useState<Record<string, boolean>>({});
  const [expandedRoles, setExpandedRoles] = useState<Record<string, boolean>>({
    "U1-RN": true,
  });

  const handleCollapseAll = () => {
    setExpandedUnits({});
    setExpandedRoles({});
  };

  const handleExpandAll = () => {
    const allUnits = Object.fromEntries(units.map((unit) => [unit.id, true]));
    setExpandedUnits(allUnits);
  };

  const toggleUnit = (unitId: string) =>
    setExpandedUnits((prev) => ({ ...prev, [unitId]: !prev[unitId] }));

  const toggleRole = (key: string) =>
    setExpandedRoles((prev) => ({ ...prev, [key]: !prev[key] }));

  return {
    expandedUnits,
    expandedRoles,
    handleCollapseAll,
    handleExpandAll,
    toggleUnit,
    toggleRole,
  };
}

function useBoardDateNavigation() {
  const [anchorDateStr, setAnchorDateStr] = useQueryState(
    "anchor",
    parseAsString.withDefault(getTodayString()),
  );

  const [viewMode, setViewMode] = useState<ViewMode>("ROLE");
  const [groupingMode, setGroupingMode] = useState<"ROLE" | "BUDGET">("ROLE");

  const anchorDate = useMemo(() => new Date(anchorDateStr), [anchorDateStr]);
  const visibleStartDate = useMemo(() => subDays(anchorDate, 2), [anchorDate]);
  const visibleDates = useMemo(
    () => Array.from({ length: VISIBLE_DAY_COUNT }, (_, index) => addDays(visibleStartDate, index)),
    [visibleStartDate],
  );

  const pageSchedule = (dayDelta: number) => {
    setAnchorDateStr(formatDateYYYYMMDD(addDays(anchorDate, dayDelta)));
  };

  return {
    viewMode,
    setViewMode,
    groupingMode,
    setGroupingMode,
    visibleDates,
    pageSchedule,
    anchorDate,
  };
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

  const [activeShift, setActiveShift] = useState<Shift | null>(null);

  const {
    handleDragEnd,
    pendingSlotId,
    validationPreview,
    setPendingSlotId,
    setValidationPreview,
  } = useDragValidation({
    selectedFacility,
    scheduleId,
    scheduleVersion,
    draftState,
    dragDisabled,
    appendDraftPatch,
    setDraftConflicts,
    setHasPendingValidation,
  });

  const {
    expandedUnits,
    expandedRoles,
    handleCollapseAll,
    handleExpandAll,
    toggleUnit,
    toggleRole,
  } = useBoardExpansion(units);

  const { viewMode, setViewMode, groupingMode, setGroupingMode, visibleDates, pageSchedule } =
    useBoardDateNavigation();

  const unitGroups = useMemo(() => {
    return units.map((unit) => ({
      unit,
      staff: staffList.filter((s) => s.unitId === unit.id),
    }));
  }, [staffList, units]);

  const staffByUnit = useMemo(() => {
    const map = new Map<string, Staff[]>();
    for (const unit of units) {
      map.set(unit.id, staffList.filter((s) => s.unitId === unit.id));
    }
    return map;
  }, [staffList, units]);

  const boardMetrics = useBoardMetrics(
    shifts, units, staffByUnit, visibleDates, viewMode, groupingMode,
  );

  const resolveTargetShiftId = (unitId: string, dateStr: string, shiftKey: ShiftTypeKey) => {
    return targetShiftIds.get(`${unitId}:${dateStr}:${shiftKey}`) ?? null;
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
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

        <BoardHeader
          visibleDates={visibleDates}
          pageSchedule={pageSchedule}
          viewMode={viewMode}
          setViewMode={setViewMode}
          groupingMode={groupingMode}
          setGroupingMode={setGroupingMode}
          clearDraft={clearDraft}
          draftState={draftState}
          units={units}
          handleCollapseAll={handleCollapseAll}
          handleExpandAll={handleExpandAll}
          dragDisabled={dragDisabled}
          activeRun={activeRun}
        />

        <div
          className={cn(
            "relative flex-1 bg-background xl:min-h-0",
            dragDisabled
              ? "overflow-hidden overscroll-contain touch-none"
              : "overflow-auto",
          )}
        >
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
                  isExpanded={expandedUnits[group.unit.id] ?? false}
                  onToggle={() => toggleUnit(group.unit.id)}
                  roleState={expandedRoles}
                  toggleRole={toggleRole}
                  pendingSlotId={pendingSlotId}
                  validationPreview={validationPreview}
                  dragDisabled={dragDisabled}
                  resolveTargetShiftId={resolveTargetShiftId}
                  boardMetrics={boardMetrics}
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
