import { useDroppable } from "@dnd-kit/core";
import React from "react";
import { ValidationLevel } from "@/hooks/proto-mocks";
import { cn } from "@/lib/utils";
import { CELL_WIDTH } from "@/components/schedule-board/schedule-board";
import { Ban, Plus } from "lucide-react";

// droppable
export default function TimelineSlot({
  id,
  data,
  children,
  isEvenDay,
  isLastShift,
  isSimulatingTarget,
  simulationResult,
}: any) {
  const { setNodeRef, isOver } = useDroppable({ id, data });

  // Check if this slot is empty (has no children passed to it)
  // React.Children.count is a safe way to check
  const isEmpty = React.Children.count(children) === 0;

  // --- DYNAMIC BACKGROUND LOGIC ---
  let bgClass = isEvenDay ? "bg-slate-50/40" : "bg-white";
  let ringClass = "";

  if (isOver) {
    // Default Hover State
    bgClass = "bg-blue-50";
    ringClass = "ring-2 ring-blue-400 z-10";

    // SIMULATION OVERRIDES (The "Yellow/Red" Feedback)
    if (isSimulatingTarget && simulationResult) {
      if (
        simulationResult.complianceStatus === ValidationLevel.VALIDATION_WARNING
      ) {
        // YELLOW ZONE (Overtime / Cost Warning)
        bgClass = "bg-amber-50 pattern-diagonal-lines pattern-amber-100"; // hypothetical pattern class
        ringClass = "ring-2 ring-amber-400 z-20";
      } else if (
        simulationResult.complianceStatus ===
        ValidationLevel.VALIDATION_CRITICAL
      ) {
        // RED ZONE (Blocked)
        bgClass = "bg-red-50";
        ringClass = "ring-2 ring-red-500 z-20";
      } else if (
        simulationResult.complianceStatus === ValidationLevel.VALIDATION_OK
      ) {
        // GREEN ZONE (Good move)
        bgClass = "bg-emerald-50";
        ringClass = "ring-2 ring-emerald-400 z-20";
      }
    }
  }

  return (
    <div
      ref={setNodeRef}
      className={cn(
        CELL_WIDTH,
        "border-r border-slate-100 relative flex flex-col justify-center transition-colors duration-200",
        isLastShift && "border-r-slate-300",
        bgClass, // Applied dynamic background
        ringClass, // Applied dynamic ring
      )}
    >
      {children}

      {/* Phantom Add Button */}
      {/* Only show if empty and not currently dragging over */}
      {isEmpty && !isOver && (
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover/slot:opacity-100 transition-opacity pointer-events-none">
          <div className="bg-slate-100 text-slate-400 rounded-md p-1">
            <Plus size={12} />
          </div>
        </div>
      )}

      {/* Error Icon inside slot if Critical */}
      {isOver &&
        isSimulatingTarget &&
        simulationResult?.complianceStatus ===
          ValidationLevel.VALIDATION_CRITICAL && (
          <div className="absolute inset-0 flex items-center justify-center bg-red-100/50">
            <Ban className="text-red-500 opacity-50" size={24} />
          </div>
        )}
    </div>
  );
}
