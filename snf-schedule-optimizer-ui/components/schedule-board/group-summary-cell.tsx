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
        ? "bg-[#FBC02D]"
        : "bg-[#28A745]";
  // Lighter background for totals to distinguish from rows
  const bgColor = isTotal
    ? "bg-transparent"
    : status === "critical"
      ? "bg-red-50"
      : status === "warning"
        ? "bg-[#FFF8E1]"
        : "bg-[#F4F6F8]";
  const textColor =
    status === "critical"
      ? "text-red-700"
      : status === "warning"
        ? "text-[#FBC02D]"
        : "text-[#6C757D]";
  const widthPct = Math.min(filledPct * 100, 100);

  return (
    <div
      className={cn(
        CELL_WIDTH,
        "group/cell relative flex h-full flex-col justify-end border-r border-[#E0E0E0]",
        isToday ? "bg-[#DFFFEA]" : bgColor,
      )}
    >
      {/* Percentage Text */}
      <div
        className={cn(
          "absolute inset-0 z-10 flex items-center justify-center text-[10px] font-medium",
          textColor,
        )}
      >
        {label}
      </div>
      {/* Progress Bar Background */}
      <div className="absolute bottom-0 h-1.5 w-full bg-[#E9EEF1]">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${widthPct}%` }}
          className={cn("h-full", barColor)}
        />
      </div>
    </div>
  );
}
