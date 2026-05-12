import React from "react";
import { UICalendarDay } from "@/types/scheduling";

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
  // Conditionally adjust the height/padding based on the view mode
  // mb-8 adds a little space below the 2-row grid to keep the legend from floating too high
  const gridContainerClasses = isTwoWeekView
    ? "mb-8 grid grid-cols-7 gap-1 sm:gap-2"
    : "grid grid-cols-7 gap-1 sm:gap-2";

  return (
    <div className={gridContainerClasses}>
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
                className={`w-2.5 h-2.5 rounded-full shadow ${getIndicatorDotClass(day.dayHPRDPercentage)}`}
                title={`HPRD Coverage: ${day.dayHPRDPercentage.toFixed(0)}%`}
              ></div>
              {/* The Percentage Text */}
              <span
                className={`text-xs font-bold ${day.dayHPRDPercentage >= 100 ? "text-green-700" : "text-gray-700"}`}
              >
                {day.dayHPRDPercentage.toFixed(0)}%
              </span>
            </div>
          ) : day.isCurrentMonth && !day.isSelectable ? (
            // Disabled/Future State
            <div className="text-xs text-gray-400 font-semibold italic">
              Future
            </div>
          ) : (
            // Padding cells (N/A)
            <div className="w-6 h-6"></div> // Placeholder for alignment
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
  let classes =
    "relative flex h-20 flex-col items-stretch justify-start rounded-lg border border-[#E0E0E0] bg-white p-1 text-center shadow-none transition duration-150 ease-in-out sm:h-24";

  if (!day.isSelectable) {
    classes += " cursor-default bg-[#F4F6F8] opacity-50";
  } else {
    classes +=
      " cursor-pointer hover:border-[#28A745] hover:bg-[#DFFFEA] active:scale-[0.99]";
  }

  if (selectedDayDateString === day.dateString) {
    classes += " ring-2 ring-[#168039] ring-offset-2 ring-offset-white";
  }

  if (!day.isCurrentMonth) {
    classes = classes.replace("bg-white", "bg-[#F4F6F8]");
  }

  return classes;
};

// Day number classes (to make today stand out)
function getDayNumberClasses(day: UICalendarDay): string {
  let classes =
    "mx-auto mb-1 flex h-7 w-7 items-center justify-center rounded-lg text-xs font-medium transition duration-150";

  if (day.isToday && day.isCurrentMonth) {
    classes += " bg-[#168039] text-white";
  } else if (day.isCurrentMonth && day.isSelectable) {
    classes += " text-[#212529]";
  } else {
    classes += " text-[#6C757D]";
  }
  return classes;
}

// Helper to determine the color of the coverage dot based on HPRD %
function getIndicatorDotClass(percentage: number): string {
  // CRITICAL: Below 70%
  if (percentage < 70) {
    return "bg-red-500";
  }
  // WARNING: 70% to 99%
  if (percentage < 100) {
    return "bg-[#FBC02D]";
  }
  // IDEAL: 100% and above
  return "bg-[#28A745]";
}
