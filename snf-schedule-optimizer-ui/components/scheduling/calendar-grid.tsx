import React from "react";
import { UICalendarDay } from "@/types/scheduling";
import { cn } from "@/lib/utils";

interface CalendarGridProps {
  calendarDays: UICalendarDay[];
  openShiftDetails: (day: UICalendarDay) => void;
  selectedDayDateString: string | null;
  isTwoWeekView: boolean;
}

// Main container classes (handles overall day appearance, including interactivity)
export function CalendarGrid({
  calendarDays,
  openShiftDetails,
  selectedDayDateString,
  isTwoWeekView,
}: CalendarGridProps) {
  return (
    <div className={cn("grid grid-cols-7 gap-1 sm:gap-2", isTwoWeekView && "mb-8")}>
      {calendarDays.map((day) => (
        <div
          key={day.dateString}
          onClick={() => day.isSelectable && openShiftDetails(day)}
          className={getContainerClasses(day, selectedDayDateString)}
        >
          {/* Day Number */}
          <span className={getDayNumberClasses(day)}>{day.dayOfMonth}</span>

          {/* Single Overview Block */}
          {day.schedule && day.isSelectable ? (
            <div className="flex items-center space-x-1">
              {/* The Dot */}
              <div
                className={cn(
                  "h-2.5 w-2.5 rounded-full shadow",
                  getIndicatorDotClass(day.dayHPRDPercentage),
                )}
                title={`HPRD Coverage: ${day.dayHPRDPercentage.toFixed(0)}%`}
              />
              {/* The Percentage Text */}
              <span
                className={cn(
                  "text-xs font-bold",
                  day.dayHPRDPercentage >= 100 ? "text-green-700" : "text-slate-700",
                )}
              >
                {day.dayHPRDPercentage.toFixed(0)}%
              </span>
            </div>
          ) : day.isCurrentMonth && !day.isSelectable ? (
            // Disabled/Future State
            <div className="text-xs font-semibold italic text-muted-foreground">
              Future
            </div>
          ) : (
            // Padding cells (N/A)
            <div className="h-6 w-6" />
          )}
        </div>
      ))}
    </div>
  );
}

// Main container classes (handles overall day appearance, including interactivity)
const getContainerClasses = (
  day: UICalendarDay,
  selectedDayDateString: string | null,
): string => {
  return cn(
    "relative flex h-20 flex-col items-stretch justify-start rounded-lg border border-border p-1 text-center shadow-none transition duration-150 ease-in-out sm:h-24",
    !day.isCurrentMonth || !day.isSelectable ? "bg-background" : "bg-card",
    day.isSelectable
      ? "cursor-pointer hover:border-primary/70 hover:bg-accent active:scale-[0.99]"
      : "cursor-default opacity-50",
    selectedDayDateString === day.dateString && "ring-2 ring-ring ring-offset-2 ring-offset-card",
  );
};

// Day number classes (to make today stand out)
function getDayNumberClasses(day: UICalendarDay): string {
  return cn(
    "mx-auto mb-1 flex h-7 w-7 items-center justify-center rounded-lg text-xs font-medium transition duration-150",
    day.isToday && day.isCurrentMonth
      ? "bg-primary text-primary-foreground"
      : day.isCurrentMonth && day.isSelectable
        ? "text-foreground"
        : "text-muted-foreground",
  );
}

// Helper to determine the color of the coverage dot based on HPRD %
function getIndicatorDotClass(percentage: number): string {
  // CRITICAL: Below 70%
  if (percentage < 70) {
    return "bg-red-500";
  }
  // WARNING: 70% to 99%
  if (percentage < 100) {
    return "bg-amber-400";
  }
  // IDEAL: 100% and above
  return "bg-green-600";
}
