import React, {useEffect, useState} from 'react';
import {UICalendarDay} from '@/types/scheduling';

interface CalendarGridProps {
    calendarDays: UICalendarDay[];
    openShiftDetails: (day: UICalendarDay) => void;
    selectedDayDateString: string | null;
    isTwoWeekView: boolean;
}

// Main container classes (handles overall day appearance, including interactivity)
export const CalendarGrid: React.FC<CalendarGridProps> = (
    {
        calendarDays,
        openShiftDetails,
        selectedDayDateString,
        isTwoWeekView
    }) => {
    const [hasMounted, setHasMounted] = useState(false);

    console.log("Rendering CalendarGrid with", calendarDays.length, "days. TwoWeekView:", isTwoWeekView, "received: ", calendarDays.length, "passed calendar days.");
    // print each for debug
    calendarDays.forEach((day => {
        console.log("Day:", day.dateString, "Selectable:", day.isSelectable, "HPRD %:", day.dayHPRDPercentage, "schedule length", day.schedule ? day.schedule.shifts.length : 0);
    }));

    // Conditionally adjust the height/padding based on the view mode
    // mb-8 adds a little space below the 2-row grid to keep the legend from floating too high
    const gridContainerClasses = isTwoWeekView ? 'grid grid-cols-7 gap-1 sm:gap-2 mb-8' : 'grid grid-cols-7 gap-1 sm:gap-2';


    useEffect(() => {
        console.log("CalendarGrid mounted.");
        setHasMounted(true);
    }, []);

    return (
        <div className={gridContainerClasses}>
            {calendarDays.map(day => (
                <div key={day.dateString}
                     onClick={() => day.isSelectable && openShiftDetails(day)}
                     className={getContainerClasses(day, selectedDayDateString)}>

                    {/* Day Number */}
                    <span className={getDayNumberClasses(day)}>
            {day.dayOfMonth}
          </span>

                    {/* Single Overview Block */}
                    {day.schedule && day.isSelectable && hasMounted ? (
                        <div className="flex items-center space-x-1">
                            {/* The Dot */}
                            <div
                                className={`w-2.5 h-2.5 rounded-full shadow ${getIndicatorDotClass(day.dayHPRDPercentage)}`}
                                title={`HPRD Coverage: ${day.dayHPRDPercentage.toFixed(0)}%`}
                            ></div>
                            {/* The Percentage Text */}
                            <span
                                className={`text-xs font-bold ${day.dayHPRDPercentage >= 100 ? 'text-green-700' : 'text-gray-700'}`}>
                                    {day.dayHPRDPercentage.toFixed(0)}%
                                </span>
                        </div>
                    ) : day.isCurrentMonth && !day.isSelectable ? (
                        // Disabled/Future State
                        <div className="text-xs text-gray-400 font-semibold italic">Future</div>
                    ) : (
                        // Padding cells (N/A)
                        <div className="w-6 h-6"></div> // Placeholder for alignment
                    )}
                </div>
            ))}
        </div>
    );
};

// Main container classes (handles overall day appearance, including interactivity)
const getContainerClasses = (day: UICalendarDay, selectedDayDateString: string | null): string => {
    let classes = 'text-center relative h-20 sm:h-24 flex flex-col justify-start items-stretch p-0.5 rounded-lg border border-gray-200 shadow-sm transition duration-150 ease-in-out';

    if (!day.isSelectable) {
        classes += ' opacity-50 bg-gray-50 cursor-default';
    } else {
        classes += ' bg-white cursor-pointer hover:shadow-lg active:shadow-inner active:scale-[0.98]';
    }

    if (selectedDayDateString === day.dateString) {
        classes += ' ring-4 ring-indigo-400 ring-offset-2';
    }

    if (!day.isCurrentMonth) {
        classes = classes.replace('bg-white', 'bg-gray-100');
    }

    return classes;
};

// Day number classes (to make today stand out)
const getDayNumberClasses = (day: UICalendarDay): string => {
    let classes = 'transition duration-150 mx-auto w-6 h-6 flex items-center justify-center rounded-full mb-0.5 text-xs font-medium';

    if (day.isToday && day.isCurrentMonth) {
        classes += ' bg-indigo-600 text-white font-bold shadow-md';
    } else if (day.isCurrentMonth && day.isSelectable) {
        classes += ' text-gray-800';
    } else {
        classes += ' text-gray-400';
    }
    return classes;
};

// Helper to determine the color of the coverage dot based on HPRD %
const getIndicatorDotClass = (percentage: number): string => {
    // CRITICAL: Below 70%
    if (percentage < 70) {
        return 'bg-red-500';
    }
    // WARNING: 70% to 99%
    if (percentage < 100) {
        return 'bg-yellow-400';
    }
    // IDEAL: 100% and above
    return 'bg-green-500';
};