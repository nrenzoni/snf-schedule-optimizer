// --- LEVEL 2: ROLE GROUP (Nested) ---
import { STAFF_COL_WIDTH } from "@/components/schedule-board/schedule-board";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp } from "lucide-react";
import { format, isSameDay } from "date-fns";
import {
  MoveValidationPreview,
  Shift,
  SHIFT_TYPES,
  ShiftTypeKey,
  Staff,
} from "@/types/scheduler";
import GroupSummaryCell from "@/components/schedule-board/group-summary-cell";
import { AnimatePresence, motion } from "framer-motion";
import TimelineSlot from "@/components/schedule-board/timeline-slot";
import ShiftCard from "@/components/schedule-board/shift-card";
import { calculateCellMetric } from "@/components/schedule-board/utils";
import ConfirmDialog from "@/components/ui/confirm-dialog";
import { useState } from "react";

interface RoleGroupProps {
  unitId: string;
  groupKey: string;
  label: string;
  staffMembers: Staff[];
  shifts: Shift[];
  dates: Date[];
  viewMode: "ROLE" | "BUDGET";
  groupingMode: "ROLE" | "BUDGET";
  isExpanded: boolean;
  onToggle: () => void;
  pendingSlotId: string | null;
  validationPreview: MoveValidationPreview | null;
  dragDisabled: boolean;
  resolveTargetShiftId: (unitId: string, dateStr: string, shiftKey: ShiftTypeKey) => string | null;
  onDeleteShift: (shift: Shift) => Promise<boolean>;
}

export default function RoleGroup({
  unitId,
  groupKey,
  label,
  staffMembers,
  shifts,
  dates,
  viewMode,
  groupingMode,
  isExpanded,
  onToggle,
  pendingSlotId,
  validationPreview,
  dragDisabled,
  resolveTargetShiftId,
  onDeleteShift,
}: RoleGroupProps) {
  const [pendingDelete, setPendingDelete] = useState<Shift | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  return (
    <>
      <div className="border-b border-border bg-card last:border-b-0">
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
              "sticky left-0 z-20 flex cursor-pointer items-center gap-2 border-r border-border bg-background px-3 py-1.5 pl-8 hover:bg-accent",
            )}
          >
            {isExpanded ? (
              <ChevronUp size={14} className="text-slate-400" />
            ) : (
              <ChevronDown size={14} className="text-slate-400" />
            )}
            <div className="text-xs font-medium text-muted-foreground">{label}</div>
          </div>
          <div className="flex items-stretch">
            {dates.map((date: Date) => {
              const dateStr = format(date, "yyyy-MM-dd");
              const isToday = isSameDay(date, new Date());
              return (
                <div key={`${groupKey}-${dateStr}`} className="flex w-[216px] min-w-[216px] items-stretch">
                  <div className="flex min-h-full items-stretch">
                    {(Object.keys(SHIFT_TYPES) as ShiftTypeKey[]).map((shiftKey) => {
                      const metric = calculateCellMetric(
                        shifts,
                        { unitId: unitId, groupId: groupKey },
                        viewMode,
                        groupingMode,
                        staffMembers,
                        dateStr,
                        shiftKey,
                      );
                      return (
                        <GroupSummaryCell
                          key={`${groupKey}-${dateStr}-${shiftKey}`}
                          metric={metric}
                          isToday={isToday}
                          compact
                        />
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <AnimatePresence initial={false}>
          {isExpanded && (
            <motion.div
              initial={{ height: 0 }}
              animate={{ height: "auto" }}
              exit={{ height: 0 }}
              className="overflow-hidden"
            >
              {staffMembers.map((staff: Staff) => (
                <div
                  key={staff.rowId}
                  className="group/row flex min-h-14 items-stretch border-b border-border hover:bg-accent"
                >
                  <div
                    className={cn(
                      STAFF_COL_WIDTH,
                      "sticky left-0 z-10 flex flex-col justify-center border-r border-border bg-card px-4 pl-8 group-hover/row:bg-accent",
                    )}
                  >
                    <div className="truncate text-sm font-medium text-foreground">{staff.name}</div>
                    <div className="text-[10px] font-normal text-muted-foreground">{staff.fte} FTE</div>
                  </div>
                  <div className="flex items-stretch">
                    {dates.map((date: Date, dayIndex: number) => {
                      const dateStr = format(date, "yyyy-MM-dd");
                      const isToday = isSameDay(date, new Date());

                      return (
                        <div key={`${staff.rowId}-${dateStr}`} className="flex w-[216px] min-w-[216px] items-stretch">
                          <div className="flex min-h-full items-stretch">
                            {(Object.keys(SHIFT_TYPES) as ShiftTypeKey[]).map((shiftKey, idx) => {
                              const slotId = `${staff.rowId}::${dateStr}::${shiftKey}`;
                              const targetShiftId = resolveTargetShiftId(unitId, dateStr, shiftKey);
                              const slotShifts = shifts.filter(
                                (s: Shift) =>
                                  s.rowId === staff.rowId &&
                                  s.unitId === unitId &&
                                  s.dateStr === dateStr &&
                                  s.shiftType === shiftKey,
                              );

                              return (
                                <TimelineSlot
                                  key={`${staff.rowId}-${dateStr}-${shiftKey}`}
                                  id={slotId}
                                  data={{
                                    rowId: staff.rowId,
                                    staffId: staff.id,
                                    dateStr,
                                    typeKey: shiftKey,
                                    shiftId: targetShiftId ?? "",
                                  }}
                                  isEvenDay={dayIndex % 2 === 0}
                                  isToday={isToday}
                                  isLastShift={idx === 2}
                                  isPendingTarget={pendingSlotId === slotId}
                                  validationPreview={pendingSlotId === slotId ? validationPreview : null}
                                >
                                  {slotShifts.map((shift) => (
                                    <ShiftCard
                                      key={shift.id}
                                      shift={shift}
                                      mode={viewMode}
                                      dragDisabled={dragDisabled}
                                      onDelete={dragDisabled ? undefined : setPendingDelete}
                                    />
                                  ))}
                                </TimelineSlot>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <ConfirmDialog
        isOpen={pendingDelete !== null}
        title="Delete shift assignment?"
        description={
          pendingDelete
            ? `Remove ${pendingDelete.employeeName} from this shift and stage the deletion for the next optimization run?`
            : ""
        }
        confirmLabel="Delete assignment"
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          if (!pendingDelete) {
            return;
          }
          setIsDeleting(true);
          void onDeleteShift(pendingDelete)
            .then((didClose) => {
              if (didClose) {
                setPendingDelete(null);
              }
            })
            .finally(() => {
              setIsDeleting(false);
            });
        }}
        isDestructive
        isPending={isDeleting}
      />
    </>
  );
}
