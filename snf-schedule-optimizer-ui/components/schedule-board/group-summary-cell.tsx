import { GroupMetric } from "@/types/scheduler";
import { cn } from "@/lib/utils";
import { CELL_WIDTH } from "@/components/schedule-board/schedule-board";
import { motion } from "framer-motion";
import React from "react";

// Header Visualization
export default function GroupSummaryCell({
  metric,
  isTotal,
  isToday,
}: {
  metric: GroupMetric;
  isTotal?: boolean;
  isToday?: boolean;
}) {
  const { filledPct, label, status } = metric;
  const barColor =
    status === "critical"
      ? "bg-red-500"
      : status === "warning"
        ? "bg-amber-500"
        : "bg-emerald-500";
  // Lighter background for totals to distinguish from rows
  const bgColor = isTotal
    ? "bg-transparent"
    : status === "critical"
      ? "bg-red-50"
      : status === "warning"
        ? "bg-amber-50"
        : "bg-slate-50";
  const textColor =
    status === "critical"
      ? "text-red-700"
      : status === "warning"
        ? "text-amber-700"
        : "text-slate-600";
  const widthPct = Math.min(filledPct * 100, 100);

  return (
    <div
      className={cn(
        CELL_WIDTH,
        "h-full flex flex-col justify-end border-r border-slate-200/50 relative group/cell",
        isToday ? "bg-blue-50/30" : bgColor,
      )}
    >
      {/* Percentage Text */}
      <div
        className={cn(
          "absolute inset-0 flex items-center justify-center text-[10px] font-bold z-10",
          textColor,
        )}
      >
        {label}
      </div>
      {/* Progress Bar Background */}
      <div className="w-full h-1.5 bg-slate-200/50 absolute bottom-0">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${widthPct}%` }}
          className={cn("h-full", barColor)}
        />
      </div>
    </div>
  );
}
