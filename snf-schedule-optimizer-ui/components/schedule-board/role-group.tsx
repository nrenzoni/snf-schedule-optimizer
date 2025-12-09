// --- LEVEL 2: ROLE GROUP (Nested) ---
import { STAFF_COL_WIDTH } from "@/components/schedule-board/schedule-board";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp } from "lucide-react";
import { format } from "date-fns";
import { Shift, SHIFT_TYPES, ShiftTypeKey, Staff } from "@/types/scheduler";
import GroupSummaryCell from "@/components/schedule-board/group-summary-cell";
import { AnimatePresence, motion } from "framer-motion";
import TimelineSlot from "@/components/schedule-board/timeline-slot";
import ShiftCard from "@/components/schedule-board/shift-card";
import { calculateCellMetric } from "@/components/schedule-board/utils";

export default function RoleGroup({
  groupKey,
  label,
  staffMembers,
  shifts,
  dates,
  viewMode,
  groupingMode,
  isExpanded,
  onToggle,
  simulatingSlotId,
  simulationResult,
}: any) {
  return (
    <div className="border-b last:border-b-0 bg-white">
      <div className="flex bg-slate-50 border-b border-slate-200">
        <div
          onClick={onToggle}
          className={cn(
            STAFF_COL_WIDTH,
            "sticky left-0 z-20 flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-slate-100 border-r border-slate-200 bg-slate-50 pl-8",
          )}
        >
          {isExpanded ? (
            <ChevronUp size={14} className="text-slate-400" />
          ) : (
            <ChevronDown size={14} className="text-slate-400" />
          )}
          <div className="text-xs font-semibold text-slate-600">{label}</div>
        </div>
        <div className="flex">
          {dates.map((date: Date) => {
            const dateStr = format(date, "yyyy-MM-dd");
            return (Object.keys(SHIFT_TYPES) as ShiftTypeKey[]).map(
              (shiftKey) => {
                const metric = calculateCellMetric(
                  shifts,
                  { unitId: "", groupId: groupKey },
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
                  />
                );
              },
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
                key={staff.id}
                className="flex border-b border-slate-100 hover:bg-slate-50 h-14 group"
              >
                <div
                  className={cn(
                    STAFF_COL_WIDTH,
                    "sticky left-0 bg-white z-10 flex flex-col justify-center px-4 border-r border-slate-200 group-hover:bg-slate-50 pl-8",
                  )}
                >
                  <div className="font-medium text-sm text-slate-800 truncate">
                    {staff.name}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    {staff.fte} FTE
                  </div>
                </div>
                <div className="flex">
                  {dates.map((date: Date, dayIndex: number) => {
                    const dateStr = format(date, "yyyy-MM-dd");
                    return (Object.keys(SHIFT_TYPES) as ShiftTypeKey[]).map(
                      (shiftKey, idx) => {
                        const slotId = `${staff.id}::${dateStr}::${shiftKey}`;
                        return (
                          <TimelineSlot
                            key={`${staff.id}-${dateStr}-${shiftKey}`}
                            id={`${staff.id}::${dateStr}::${shiftKey}`}
                            data={{
                              staffId: staff.id,
                              dateStr,
                              typeKey: shiftKey,
                            }}
                            isEvenDay={dayIndex % 2 === 0}
                            isLastShift={idx === 2}
                            isSimulatingTarget={simulatingSlotId === slotId}
                            simulationResult={simulationResult}
                          >
                            {shifts
                              .filter(
                                (s: Shift) =>
                                  s.staffId === staff.id &&
                                  s.dateStr === dateStr &&
                                  s.shiftType === shiftKey,
                              )
                              .map((s: Shift) => (
                                <ShiftCard
                                  key={s.id}
                                  shift={s}
                                  mode={viewMode}
                                />
                              ))}
                          </TimelineSlot>
                        );
                      },
                    );
                  })}
                </div>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
