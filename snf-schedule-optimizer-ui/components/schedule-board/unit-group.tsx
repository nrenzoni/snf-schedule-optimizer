"use client";

// This calculates the metrics for a specific CELL in the group header
import { AnimatePresence, motion } from "framer-motion";
// --- LEVEL 1: UNIT GROUP (Top Level) ---
import React, { useMemo } from "react";
import {
  MoveValidationPreview,
  RoleKey,
  ROLES,
  SHIFT_TYPES,
  ShiftTypeKey,
  Staff,
} from "@/types/scheduler";
import { cn } from "@/lib/utils";
import { STAFF_COL_WIDTH } from "@/components/schedule-board/schedule-board";
import { Building2, ChevronDown, ChevronUp } from "lucide-react";
import { format, isSameDay } from "date-fns";
import GroupSummaryCell from "@/components/schedule-board/group-summary-cell";
import RoleGroup from "@/components/schedule-board/role-group";
import { calculateCellMetric } from "@/components/schedule-board/utils";
import { Shift, SimulatedUnit, ViewMode } from "@/types/scheduler";

type NestedGroup = {
  key: string;
  label: string;
  staff: Staff[];
};

interface UnitGroupProps {
  unit: SimulatedUnit;
  staffMembers: Staff[];
  shifts: Shift[];
  dates: Date[];
  viewMode: ViewMode;
  groupingMode: "ROLE" | "BUDGET";
  isExpanded: boolean;
  onToggle: () => void;
  roleState: Record<string, boolean>;
  toggleRole: (key: string) => void;
  pendingSlotId: string | null;
  validationPreview: MoveValidationPreview | null;
  dragDisabled: boolean;
  resolveTargetShiftId: (unitId: string, dateStr: string, shiftKey: ShiftTypeKey) => string | null;
}

export default function UnitGroup({
  unit,
  staffMembers,
  shifts,
  dates,
  viewMode,
  groupingMode,
  isExpanded,
  onToggle,
  roleState,
  toggleRole,
  pendingSlotId,
  validationPreview,
  dragDisabled,
  resolveTargetShiftId,
}: UnitGroupProps) {
  // 1. Group Data inside this Unit
  const nestedGroups = useMemo(() => {
    if (groupingMode === "ROLE") {
      return (Object.keys(ROLES) as RoleKey[])
        .map((role) => ({
          key: role,
          label: ROLES[role].label,
          staff: staffMembers.filter((s: Staff) => s.role === role),
        }))
        .filter((g) => g.staff.length > 0);
    } else {
      const groups: Record<string, Staff[]> = {};
      staffMembers.forEach((s: Staff) => {
        const group = ROLES[s.role].budgetGroup;
        if (!groups[group]) groups[group] = [];
        groups[group].push(s);
      });
      return Object.entries(groups).map(([key, staff]) => ({
        key,
        label: `${key} Dept`,
        staff,
      }));
    }
  }, [staffMembers, groupingMode]);

  return (
    <div className="mb-4 overflow-hidden rounded-lg border border-border bg-card shadow-none">
      {/* UNIT HEADER */}
      <div className="flex border-b border-border bg-background">
        <div
          onClick={onToggle}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              onToggle();
            }
          }}
          role="button"
          tabIndex={0}
          aria-expanded={isExpanded}
          className={cn(
            STAFF_COL_WIDTH,
            "sticky left-0 z-30 flex cursor-pointer items-center gap-2 border-r border-border bg-background px-3 py-2 hover:bg-accent",
          )}
        >
          {isExpanded ? (
            <ChevronUp size={16} className="text-slate-700" />
          ) : (
            <ChevronDown size={16} className="text-slate-700" />
          )}
          <div className="flex flex-col">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Building2 size={14} /> {unit.label}
            </div>
            <div className="text-[10px] font-normal text-muted-foreground">
              {staffMembers.length} Staff
            </div>
          </div>
        </div>
        <div className="flex">
          {dates.map((date: Date) => {
            const dateStr = format(date, "yyyy-MM-dd");
            const isToday = isSameDay(date, new Date());
            return (Object.keys(SHIFT_TYPES) as ShiftTypeKey[]).map(
              (shiftKey) => {
                const metric = calculateCellMetric(
                  shifts,
                  { unitId: unit.id },
                  viewMode,
                  groupingMode,
                  staffMembers,
                  dateStr,
                  shiftKey,
                );
                return (
                  <GroupSummaryCell
                    key={`${unit.id}-${dateStr}-${shiftKey}`}
                    metric={metric}
                    isTotal
                    isToday={isToday}
                  />
                );
              },
            );
          })}
        </div>
      </div>

      {/* NESTED BODY */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: "auto" }}
            exit={{ height: 0 }}
            className="overflow-hidden bg-background"
          >
            {nestedGroups.map((group: NestedGroup) => (
              <RoleGroup
                key={group.key}
                groupKey={group.key}
                label={group.label}
                staffMembers={group.staff}
                shifts={shifts}
                dates={dates}
                viewMode={viewMode}
                groupingMode={groupingMode}
                isExpanded={!!roleState[`${unit.id}-${group.key}`]}
                onToggle={() => toggleRole(`${unit.id}-${group.key}`)}
                pendingSlotId={pendingSlotId}
                validationPreview={validationPreview}
                dragDisabled={dragDisabled}
                unitId={unit.id}
                resolveTargetShiftId={resolveTargetShiftId}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
