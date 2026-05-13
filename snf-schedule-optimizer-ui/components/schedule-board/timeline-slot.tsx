import { useDroppable } from "@dnd-kit/core";
import React from "react";
import { SimulateActionResponse, ValidationLevel } from "@/hooks/proto-mocks";
import { cn } from "@/lib/utils";
import { CELL_WIDTH } from "@/components/schedule-board/schedule-board";
import { Ban, Plus } from "lucide-react";

type TimelineSlotData = {
  staffId: string;
  dateStr: string;
  typeKey: string;
};

// droppable
export default function TimelineSlot({
  id,
  data,
  children,
  isEvenDay,
  isToday,
  isLastShift,
  isSimulatingTarget,
  simulationResult,
}: {
  id: string;
  data: TimelineSlotData;
  children: React.ReactNode;
  isEvenDay: boolean;
  isToday: boolean;
  isLastShift: boolean;
  isSimulatingTarget: boolean;
  simulationResult: SimulateActionResponse | null;
}) {
  const { setNodeRef, isOver } = useDroppable({ id, data });

  // Check if this slot is empty (has no children passed to it)
  // React.Children.count is a safe way to check
  const isEmpty = React.Children.count(children) === 0;

  // --- DYNAMIC BACKGROUND LOGIC ---
  let bgClass = isToday
    ? "bg-accent"
    : isEvenDay
      ? "bg-background"
      : "bg-card";
  let ringClass = "";

  if (isOver) {
    // Default Hover State
    bgClass = "bg-accent";
    ringClass = "ring-2 ring-ring z-10";

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
        "relative flex flex-col justify-center border-r border-border transition-colors duration-200",
        isLastShift && "border-r-input",
        bgClass, // Applied dynamic background
        ringClass, // Applied dynamic ring
      )}
    >
      {children}

      {/* Phantom Add Button */}
      {/* Only show if empty and not currently dragging over */}
      {isEmpty && !isOver && (
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover/slot:opacity-100 transition-opacity pointer-events-none">
          <div className="rounded-lg bg-muted p-1 text-muted-foreground">
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
