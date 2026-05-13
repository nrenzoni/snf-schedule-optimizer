"use client";

import React, { useId, useMemo, useState } from "react";
import {
  closestCenter,
  DragOverEvent,
  defaultDropAnimationSideEffects,
  DndContext,
  DragEndEvent,
  DragOverlay,
  Modifier,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { addDays, format, isSameDay, subDays } from "date-fns";
import { cn } from "@/lib/utils";
import {
  Activity,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  DollarSign,
  LayoutList,
  TrendingUp,
  Undo2,
} from "lucide-react";
import { motion } from "framer-motion";
import {
  mockSimulateAction,
  SimulateActionResponse,
} from "@/hooks/proto-mocks";
import { toast } from "sonner";
import {
  Shift,
  SHIFT_TYPES,
  SimulatedUnit,
  Staff,
  UNITS,
  ViewMode,
} from "@/types/scheduler";
import ShiftCard from "@/components/schedule-board/shift-card";
import UnitGroup from "@/components/schedule-board/unit-group";
import { useIsFetching } from "@tanstack/react-query";
import LoadingOverlay from "../ui/loading-overlay";
import { parseAsString, useQueryState } from "nuqs";
import { formatDateYYYMMDD, TODAY_STRING } from "@/utils/scheduling-logic";
import { iconButtonVariants, segmentedButtonVariants } from "@/components/ui/styles";

// --- CONFIGURATION ---

// 1. Strict Widths for Alignment
// We use fixed widths to ensure the header and body columns align perfectly
export const STAFF_COL_WIDTH = "w-48 min-w-[12rem]";
export const CELL_WIDTH = "w-[72px] min-w-[72px]";

// --- CALCULATOR HELPER ---

const restrictToHorizontalAxis: Modifier = ({ transform }) => {
  return {
    ...transform,
    y: 0,
  };
};

const VISIBLE_DAY_COUNT = 6;

interface ScheduleBoardProps {
  initialShifts: Shift[];
  staffList: Staff[];
  units: SimulatedUnit[];
  dates: Date[];
}

// --- MAIN BOARD ---
export default function ScheduleBoard({
  initialShifts,
  staffList,
  units,
}: ScheduleBoardProps) {
  // 2. Generate a stable ID
  const dndContextId = useId();

  // This returns > 0 if any query is currently fetching in the background
  const isFetching = useIsFetching();
  const [anchorDateStr, setAnchorDateStr] = useQueryState(
    "anchor",
    parseAsString.withDefault(TODAY_STRING),
  );

  const [shifts, setShifts] = useState<Shift[]>(initialShifts);

  const [viewMode, setViewMode] = useState<ViewMode>("ROLE");
  const [groupingMode, setGroupingMode] = useState<"ROLE" | "BUDGET">("ROLE");
  const [activeShift, setActiveShift] = useState<Shift | null>(null);

  // --- SIMULATION STATE ---
  const [simulatingSlotId, setSimulatingSlotId] = useState<string | null>(null); // Which slot are we hovering?
  const [simulationResult, setSimulationResult] =
    useState<SimulateActionResponse | null>(null);

  // Expanded State for 2 Levels
  const [expandedUnits, setExpandedUnits] = useState<Record<string, boolean>>({
    U1: true,
    U2: true,
    U3: true,
    U4: true,
  });
  const [expandedRoles, setExpandedRoles] = useState<Record<string, boolean>>({
    "U1-RN": true,
  });

  // Group by Unit First
  const unitGroups = useMemo(() => {
    return Object.values(UNITS).map((unit) => ({
      unit,
      staff: staffList.filter((s) => s.unitId === unit.id),
    }));
  }, [staffList]);

  const anchorDate = useMemo(() => new Date(anchorDateStr), [anchorDateStr]);
  const visibleStartDate = useMemo(() => subDays(anchorDate, 2), [anchorDate]);
  const visibleDates = useMemo(
    () =>
      Array.from({ length: VISIBLE_DAY_COUNT }, (_, index) =>
        addDays(visibleStartDate, index),
      ),
    [visibleStartDate],
  );

  const pageSchedule = (dayDelta: number) => {
    setAnchorDateStr(formatDateYYYMMDD(addDays(anchorDate, dayDelta)));
  };

  // Expand/Collapse Logic
  const handleCollapseAll = () => {
    setExpandedUnits({});
    setExpandedRoles({});
  };
  const handleExpandAll = () => {
    const allUnits = { U1: true, U2: true, U3: true, U4: true };
    // Very simple expand all for demo
    setExpandedUnits(allUnits);
  };

  // We use a Ref to keep track of the last request to avoid race conditions
  const lastSimulatedTarget = React.useRef<string | null>(null);

  const handleDragOver = async (event: DragOverEvent) => {
    const { active, over } = event;
    if (!over) {
      setSimulationResult(null);
      setSimulatingSlotId(null);
      return;
    }

    // 1. Identify the slot we are hovering over
    const targetSlotId = String(over.id); // e.g., "st1::2023-10-01::DAY"

    // 2. Debounce: If we are still hovering the same slot, do nothing
    if (lastSimulatedTarget.current === targetSlotId) return;
    lastSimulatedTarget.current = targetSlotId;

    setSimulatingSlotId(targetSlotId);

    // 3. Extract Metadata from the ID (Parsing your format)
    // ID Format: "staffId::dateStr::shiftType"
    const [targetWorkerId, targetDateStr, targetShiftType] = targetSlotId.split("::");
    const activeShift = active.data.current?.shift as Shift | undefined;

    if (!activeShift) {
      return;
    }

    try {
      // 4. Call Mock Backend (SimulateAction RPC)
      const result = await mockSimulateAction({
        shiftId: activeShift.id,
        targetWorkerId,
        targetDateStr,
        targetShiftType,
      });

      // Only update if we are STILL hovering this slot (async check)
      if (lastSimulatedTarget.current === targetSlotId) {
        setSimulationResult(result);
      }
    } catch (e) {
      console.error("Simulation failed", e);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    // 1. Capture the LAST simulation result before we clear state
    // We use a local ref or just the current state because React state updates are batched,
    // but inside this event handler 'simulationResult' might be stale if not careful.
    // However, since dragOver happens before dragEnd, state should be fresh enough for this demo.
    const currentSimulation = simulationResult;

    // Clean up simulation/hover state immediately so the UI snaps back
    setSimulatingSlotId(null);
    setSimulationResult(null);

    if (!over) return;

    const activeData = active.data.current?.shift as Shift | undefined;
    const overData = over.data.current as
      | { staffId: string; dateStr: string; typeKey: Shift["shiftType"] }
      | undefined;

    if (!activeData || !overData) {
      return;
    }

    const { staffId, dateStr, typeKey } = overData;

    // If we dropped it in the exact same spot (same day, same shift type), do nothing.
    if (activeData.dateStr === dateStr && activeData.shiftType === typeKey) {
      return;
    }

    // Validation: Don't allow drop if simulation said CRITICAL
    if (currentSimulation?.complianceStatus === 2) {
      // ValidationLevel.CRITICAL
      toast.error("Move blocked", {
        description: currentSimulation.rejectionReason,
      });
      return;
    }

    // Validation: Staff match check (from previous turn)
    if (activeData.staffId !== staffId) return;

    // 2. SNAPSHOT FOR UNDO
    // We need to know exactly what the shift looked like BEFORE this move
    const previousShiftState = { ...activeData };

    // 3. OPTIMISTIC UPDATE
    setShifts((prev) =>
      prev.map((s) => {
        if (s.id === active.id) {
          return { ...s, dateStr, shiftType: typeKey };
        }
        return s;
      }),
    );

    // 4. TRIGGER RICH TOAST
    // We allow the toast to be dismissed or undone
    if (currentSimulation) {
      toast.custom(
        (t) => (
          // CHANGED: bg-slate-900 -> bg-white, text-white -> text-slate-900, border-slate-800 -> border-slate-200
          <div className="app-card flex w-full max-w-md items-center justify-between gap-4 p-4 text-foreground">
            <div className="flex flex-col gap-1">
              {/* Header */}
              <div className="flex items-center gap-2">
                <div
                  className={cn(
                    "w-2 h-2 rounded-full",
                    currentSimulation.complianceStatus === 1
                      ? "bg-amber-500"
                      : "bg-emerald-500",
                  )}
                />
                <span className="font-semibold text-sm">Shift Updated</span>
              </div>

              {/* Metrics Line */}
              <div className="flex items-center gap-3 text-xs text-slate-600">
                {/* Cost */}
                <div className="flex items-center gap-1">
                  <span className="text-slate-400">Cost:</span>
                  <span className="font-mono font-bold text-slate-700">
                    {currentSimulation.costDelta > 0 ? "+" : ""}$
                    {currentSimulation.costDelta}
                  </span>
                  {currentSimulation.causesOvertime && (
                    <span className="bg-red-100 text-red-700 border border-red-200 text-[9px] px-1 rounded uppercase font-bold">
                      OT
                    </span>
                  )}
                </div>
                <div className="w-px h-3 bg-slate-200" />
                {/* HPRD */}
                <div className="flex items-center gap-1">
                  <span className="text-slate-400">HPRD:</span>
                  <span
                    className={cn(
                      "font-mono font-bold flex items-center",
                      currentSimulation.hprdDelta >= 0
                        ? "text-emerald-600"
                        : "text-amber-600",
                    )}
                  >
                    {currentSimulation.hprdDelta > 0 ? "+" : ""}
                    {currentSimulation.hprdDelta.toFixed(2)}
                    <TrendingUp size={10} className="ml-0.5" />
                  </span>
                </div>
              </div>
            </div>

            {/* 5. UNDO ACTION (LIGHT THEME) */}
            <button
              onClick={() => {
                setShifts((current) =>
                  current.map((s) => {
                    if (s.id === previousShiftState.id) {
                      return previousShiftState;
                    }
                    return s;
                  }),
                );
                toast.dismiss(t);
                toast.info("Shift move undone");
              }}
              // CHANGED: Dark button -> Light gray button
              className="flex items-center gap-1 rounded border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-700 transition-colors hover:bg-slate-200"
            >
              <Undo2 size={12} /> Undo
            </button>
          </div>
        ),
        { duration: 5000 },
      );
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
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="app-card relative flex h-full flex-col overflow-hidden">
        {/* It will sit on top of everything inside this div */}
        <LoadingOverlay isVisible={isFetching > 0} />

        {/* HEADER TOOLBAR */}
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
                {format(visibleDates[0], "MMM d")} -{" "}
                {format(visibleDates[VISIBLE_DAY_COUNT - 1], "MMM d")}
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

        {/* SCROLL AREA */}
        <div className="relative flex-1 overflow-auto bg-background">
          <div className="min-w-max p-4 pb-20">
            {/* GLOBAL DATE HEADER (Stays sticky, does NOT fade) */}
            <div className="sticky top-0 z-40 mb-2 flex rounded-lg border border-border bg-card shadow-none">
              <div
                className={cn(
                  STAFF_COL_WIDTH,
                  "sticky left-0 z-50 flex items-center justify-between rounded-l-lg border-r border-border bg-card px-3 text-xs font-medium text-muted-foreground",
                )}
              >
                <span className="uppercase tracking-widest">Unit / Staff</span>
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
              <div className="hidden md:flex items-center px-3 text-xs font-medium text-slate-500">
                {units.length} units
              </div>
              {visibleDates.map((date, i) => {
                const isToday = isSameDay(date, new Date());
                return (
                  <div
                    key={i}
                    className="flex border-r border-border last:border-0"
                  >
                    <div className="flex flex-col">
                      <div
                        className={cn(
                           "w-full border-b border-border py-1.5 text-center text-xs font-medium",
                           isToday
                             ? "bg-primary text-primary-foreground"
                             : "bg-background text-foreground",
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

            {/* UNIT GROUPS */}
            {/* Changing the KEY forces React to re-trigger the animation */}
            <motion.div
              key={`${groupingMode}-${viewMode}`}
              initial={{ opacity: 0, y: 5 }} // Start slightly invisible and lower
              animate={{ opacity: 1, y: 0 }} // Fade in and slide up
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
                  isExpanded={expandedUnits[group.unit.id]}
                  onToggle={() =>
                    setExpandedUnits((prev) => ({
                      ...prev,
                      [group.unit.id]: !prev[group.unit.id],
                    }))
                  }
                  roleState={expandedRoles}
                  toggleRole={(key: string) =>
                    setExpandedRoles((prev) => ({ ...prev, [key]: !prev[key] }))
                  }
                  simulatingSlotId={simulatingSlotId}
                  simulationResult={simulationResult}
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
        {activeShift ? (
          <ShiftCard shift={activeShift} mode={viewMode} isOverlay />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
