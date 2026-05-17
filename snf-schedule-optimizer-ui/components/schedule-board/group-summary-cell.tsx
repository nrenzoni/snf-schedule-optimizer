import { GroupMetric } from "@/types/scheduler";
import { cn } from "@/lib/utils";
import { CELL_WIDTH } from "@/components/schedule-board/schedule-board";
import { motion } from "framer-motion";
import React from "react";

// Header Visualization
function GroupSummaryCell({
  metric,
  isTotal,
  isToday,
  compact = false,
}: {
  metric: GroupMetric;
  isTotal?: boolean;
  isToday?: boolean;
  compact?: boolean;
}) {
  const { filledPct, label, status } = metric;
  const barColor =
    status === "critical"
      ? "bg-red-500"
    : status === "warning"
        ? "bg-amber-400"
        : "bg-green-600";
  // Lighter background for totals to distinguish from rows
  const bgColor = isTotal
    ? "bg-transparent"
    : status === "critical"
      ? "bg-red-50"
    : status === "warning"
        ? "bg-amber-50"
        : "bg-background";
  const textColor =
    status === "critical"
      ? "text-red-700"
    : status === "warning"
        ? "text-amber-700"
        : "text-muted-foreground";
  const widthPct = Math.min(filledPct * 100, 100);

  return (
    <div
      aria-label={`${label}, ${Math.round(filledPct * 100)}% filled`}
      className={cn(
        CELL_WIDTH,
        "group/cell relative flex h-full flex-col justify-end border-r border-border",
        compact ? "min-h-10" : "min-h-14",
        isToday ? "bg-accent" : bgColor,
      )}
    >
      {/* Percentage Text */}
      <div
        className={cn(
          "absolute inset-0 z-10 flex items-center justify-center text-[10px] font-medium",
          compact && "pb-1",
          textColor,
        )}
      >
        {label}
      </div>
      {/* Progress Bar Background */}
      <div className="absolute bottom-0 h-1.5 w-full bg-muted">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${widthPct}%` }}
          className={cn("h-full", barColor)}
        />
      </div>
    </div>
  );
}
export default React.memo(GroupSummaryCell);
