import React, {useEffect, useState} from 'react';
import {CalendarDay} from '@/types/scheduling';

interface CalendarGridProps {
    calendarDays: CalendarDay[];
    openShiftDetails: (day: CalendarDay) => void;
    selectedDayDateString: string | null;
    isTwoWeekView: boolean;
}

// Main container classes (handles overall day appearance, including interactivity)
const getContainerClasses = (day: CalendarDay, selectedDayDateString: string | null): string => {
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
const getDayNumberClasses = (day: CalendarDay): string => {
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

// Determines the color for the single overview block based on HRPD %
const getDayOverallColorClass = (day: CalendarDay): string => {
    if (!day.schedule || !day.isSelectable) {
        return 'bg-gray-200';
    }
    return day.isDayHRPDMet ? 'bg-green-300 hover:bg-green-400' : 'bg-red-300 hover:bg-red-400';
};


// Main container classes (handles overall day appearance, including interactivity)
export const CalendarGrid: React.FC<CalendarGridProps> = (
    {
        calendarDays,
        openShiftDetails,
        selectedDayDateString,
        isTwoWeekView
    }) => {
    const [hasMounted, setHasMounted] = useState(false);

    // Conditionally adjust the height/padding based on the view mode
    // mb-8 adds a little space below the 2-row grid to keep the legend from floating too high
    const gridContainerClasses = isTwoWeekView ? 'grid grid-cols-7 gap-1 sm:gap-2 mb-8' : 'grid grid-cols-7 gap-1 sm:gap-2';


    useEffect(() => {
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
                    <div
                        className={`${getDayOverallColorClass(day)} flex-grow flex flex-col items-center justify-center p-0.5 rounded transition duration-100`}>
                        {day.schedule && day.isSelectable ? (
                            hasMounted ? (
                                <span
                                    className={`text-sm font-bold ${day.isDayHRPDMet ? 'text-green-800' : 'text-red-800'}`}>
            {day.dayHRPDPercentage.toFixed(0)}% MET
          </span>
                            ) : (
                                // Render a placeholder (or null) on the server/before hydration
                                // This ensures the DOM structure is the same on both server and client initially
                                <span className="text-sm font-bold opacity-0">...% MET</span>
                            )
                        ) : day.isCurrentMonth && !day.isSelectable ? (
                            // Disabled State
                            <div
                                className="flex-grow flex items-center justify-center text-xs text-gray-400 font-semibold">Future</div>
                        ) : (
                            // Padding cells
                            <div
                                className="flex-grow flex items-center justify-center text-xs text-gray-400 italic">N/A</div>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
};