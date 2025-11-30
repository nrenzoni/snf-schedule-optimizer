import {useCallback, useEffect, useMemo, useState} from 'react';
import {CalendarDay, DaySchedule as UIDaySchedule, Nurse, Shift as UIShift} from '@/types/scheduling';
import {
    formatDate,
    FOURTEEN_DAYS_AHEAD,
    generateMockScheduleMap,
    getStartOfMonth,
    getStartOfWeek,
    SHIFT_NAMES,
    TODAY,
    TODAY_STRING
} from '@/utils/scheduling-logic';
import {useSchedules} from './useSchedules';
import {DaySchedule, Shift} from "@/gen/schema/scheduling_pb";
import {schedulingClient} from "@/api/scheduling-client";

// Convert a protobuf DaySchedule/Shift into the UI DaySchedule/Shift shape
const protoShiftToUI = (p: Shift): UIShift => ({
    shiftName: (p.shiftName as any) as 'Morning' | 'Afternoon' | 'Night',
    patientCount: p.patientCount,
    requiredHPRD: (p.requiredHrpd ?? 0),
    requiredHours: p.requiredHours,
    actualHours: p.actualHours,
    isHPRDMet: p.isHrpdMet ?? false,
    nurses: (p.nurses || []).map(n => ({
        id: n.id,
        name: n.name,
        shiftHours: n.shiftHours,
        schedulingRationale: n.schedulingRationale
    }))
});

const protoDayToUI = (d: DaySchedule): UIDaySchedule => ({
    date: d.date,
    shifts: (d.shifts || []).map(protoShiftToUI)
});

// Structure for the received schedules (Map from YYYY-MM-DD string to DaySchedule)
type ScheduleMap = Map<string, UIDaySchedule>;

// Helper to generate calendar days
const generateCalendarDays = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const days: CalendarDay[] = [];

    // Padding for days before the 1st
    for (let i = 0; i < firstDay.getDay(); i++) {
        days.push({
            dayHPRDPercentage: 0,
            isCurrentMonth: false,
            isDayHPRDMet: false,
            isSelectable: false,
            isToday: false,
            schedule: null,
            date: null,
            dateString: '',
            dayOfMonth: 0,
            isPadding: true,
            coverage: 0
        })
    }

    // Actual days
    for (let i = 1; i <= lastDay.getDate(); i++) {
        // Mock coverage logic
        const coverage = Math.random() > 0.3 ? 100 : Math.floor(Math.random() * 99);
        days.push({
            dayHPRDPercentage: 0,
            isCurrentMonth: false,
            isDayHPRDMet: false,
            isSelectable: false,
            isToday: false,
            schedule: null,
            date: new Date(year, month, i),
            dateString: new Date(year, month, i).toISOString().split('T')[0],
            dayOfMonth: i,
            isPadding: false,
            coverage: coverage
        });
    }
    return days;
};

interface UseSchedulingReturn {
    currentDate: Date;
    calendarDays: CalendarDay[];
    selectedDay: CalendarDay | null;
    selectedShift: UIShift | null;
    selectedNurse: Nurse | null;
    isModalVisible: boolean;
    isTwoWeekView: boolean;
    toggleCalendarView: () => void;
    changeMonth: (offset: number) => void;
    openShiftDetails: (day: CalendarDay) => void;
    selectShift: (shift: UIShift) => void;
    openNurseDetails: (nurse: Nurse) => void;
    closeNurseDetails: () => void;
    closeModal: () => void;
    removeNurseFromShift: (nurse: Nurse) => Promise<void>;
    addNurseToShift: () => void;
    SHIFT_NAMES: typeof SHIFT_NAMES;
}

export const useScheduling = (): UseSchedulingReturn => {
    // --- State Hooks ---
    const [currentDate, setCurrentDate] = useState(getStartOfWeek(TODAY));
    const [selectedDay, setSelectedDay] = useState<CalendarDay | null>(null);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [selectedShift, setSelectedShift] = useState<UIShift | null>(null);
    const [selectedNurse, setSelectedNurse] = useState<Nurse | null>(null);
    const [isTwoWeekView, setIsTwoWeekView] = useState(true);

    // --- Data Fetching Logic (moved to useSchedules) ---
    const { schedules, isLoading, fetchSchedule } = useSchedules(currentDate);

    // 1. Memoized schedule map generated based on the current month
    const scheduleMap = useMemo(() => {
        return schedules;
    }, [schedules]);


    // 2. Computed calendar days array for the grid
    // Determine the *actual* starting date for the calendar grid display.
    // If it's a 2-week view, start from the `currentDate` (which is the start of the week).
    // If it's a full month view, calculate the first Sunday of the month's grid.
    const calendarDays = useMemo<CalendarDay[]>(() => {
        // Determine the *actual* starting date for the calendar grid display.
        // If it's a 2-week view, start from the `currentDate` (which is the start of the week).
        // If it's a full month view, calculate the first Sunday of the month's grid.
        const startDate = isTwoWeekView
            ? currentDate // Already set to the start of the current week (Sunday)
            : (() => {
                const year = currentDate.getFullYear();
                const month = currentDate.getMonth();
                const firstDayOfMonth = new Date(year, month, 1);
                const startOffset = firstDayOfMonth.getDay(); // 0-6 (Sunday to Saturday)
                // Start on the Sunday before the 1st of the month (or the 1st if it's a Sunday)
                return new Date(year, month, 1 - startOffset);
            })();


        const days: CalendarDay[] = [];
        const todayStart = new Date(TODAY);
        todayStart.setHours(0, 0, 0, 0);
        const todayStartMs = todayStart.getTime();
        const windowEndMs = FOURTEEN_DAYS_AHEAD.getTime();
        const totalDaysToRender = isTwoWeekView ? 14 : 42;

        // We no longer need the 'year' and 'month' variables from the currentDate for determining
        // `isCurrentMonth` since we want the 2-week view to not be constrained by the month.
        // However, we need to pass a context month for `isSelectable` logic if we want to keep it.
        const contextMonth = currentDate.getMonth();

        for (let i = 0; i < totalDaysToRender; i++) {
            const dayDate = new Date(startDate);
            dayDate.setDate(startDate.getDate() + i);

            const dayDateString = formatDate(dayDate);
            const schedule: UIDaySchedule | null = scheduleMap.get(dayDateString) || null;
            const dayDateMs = dayDate.getTime();

            let isDayHPRDMet = false;
            let dayHPRDPercentage = 0;

            if (schedule) {
                isDayHPRDMet = schedule.shifts.every(s => s.isHPRDMet);
                const totalRequiredHours = schedule.shifts.reduce((sum, s) => sum + s.requiredHours, 0);
                const totalActualHours = schedule.shifts.reduce((sum, s) => sum + s.actualHours, 0);

                if (totalRequiredHours > 0) {
                    dayHPRDPercentage = Math.min(100, (totalActualHours / totalRequiredHours) * 100);
                }
            }

            const isWithinWindow = dayDateMs >= todayStartMs && dayDateMs <= windowEndMs;

            // In 2-week view, all days in the 14-day window are selectable.
            // In month view, only days in the month *and* within the window are selectable.
            const isSelectable = isTwoWeekView
                ? isWithinWindow
                : dayDate.getMonth() === contextMonth && isWithinWindow; // Use contextMonth for month view

            days.push({
                coverage: 0,
                isPadding: false,
                date: dayDate,
                dateString: dayDateString,
                dayOfMonth: dayDate.getDate(),
                isToday: dayDateString === TODAY_STRING,
                // Only set `isCurrentMonth` for the month view display
                isCurrentMonth: !isTwoWeekView && dayDate.getMonth() === contextMonth,
                isSelectable: isSelectable,
                schedule,
                isDayHPRDMet: isDayHPRDMet,
                dayHPRDPercentage: dayHPRDPercentage
            });
        }
        return days;
    }, [currentDate, scheduleMap, isTwoWeekView]);

    // --- Utility Functions ---

    const closeModalImmediately = useCallback(() => {
        setSelectedDay(null);
        setSelectedShift(null);
        setSelectedNurse(null);
    }, []);

    const closeModal = useCallback(() => {
        setIsModalVisible(false);
        setTimeout(() => {
            closeModalImmediately();
        }, 300); // Wait for modal fade transition
    }, [closeModalImmediately]);

    // --- Event Handlers ---

    const toggleCalendarView = useCallback(() => {
        setIsTwoWeekView(prev => !prev);
        // When switching TO month view, reset to the current month's start date
        if (!isTwoWeekView) {
            setCurrentDate(getStartOfMonth(TODAY));
        }
        // When switching TO 2-week view, reset to the current week's start date (Sunday)
        else {
            setCurrentDate(getStartOfWeek(TODAY));
        }
        // NOTE: Must include getStartOfWeek in the dependency array or define it outside
        // the component or inside with useCallback/useMemo. Since it's a simple helper,
        // defining it outside the hook is cleaner.
    }, [isTwoWeekView]);

    const changeMonth = useCallback((direction: number): void => {
        setCurrentDate(date => {
            closeModalImmediately();
            return new Date(date.getFullYear(), date.getMonth() + direction, 1);
        });
    }, [closeModalImmediately]);

    const openShiftDetails = useCallback((day: CalendarDay): void => {
        if (!day.schedule) return;
        setSelectedDay(day);
        setSelectedShift(day.schedule.shifts[0] as any); // UI Shift
        setSelectedNurse(null);
    }, []);

    const selectShift = useCallback((shift: UIShift): void => {
        setSelectedShift(shift);
        setSelectedNurse(null);
    }, []);

    const openNurseDetails = useCallback((nurse: Nurse): void => {
        setSelectedNurse(nurse);
    }, []);

    const closeNurseDetails = useCallback((): void => {
        setSelectedNurse(null);
    }, []);

    // --- Connect-ES Mutation Action ---

    // const removeNurseFromShift = useCallback((nurse: Nurse): void => {
    //     console.log(`ACTION: Removing ${nurse.name} from ${selectedShift!.shiftName} shift on ${selectedDay!.dateString}`);
    //     // In a real app, this would trigger a Connect-ES mutation call.
    //     setSelectedNurse(null);
    // }, [selectedDay, selectedShift]);

    const removeNurseFromShift = useCallback(async (nurse: Nurse): Promise<void> => {
        if (!selectedDay || !selectedShift) return;

        const request = {
            shiftDate: selectedDay.dateString,
            shiftName: selectedShift.shiftName,
            nurseId: nurse.id,
        };

        console.log(`ACTION: Attempting to remove ${nurse.name} via RPC...`);
        try {
            // This sends the mutation to the BE
            const response = await schedulingClient.removeNurseFromShift(request);

            if (response.success) {
                console.log("Nurse removed successfully.");

                // OPTIONAL: If the response returns the updated day schedule,
                // you can update the state locally here instead of waiting for a re-fetch.
                // For simplicity, we'll just close the panel.

            } else {
                console.error("Failed to remove nurse:", response.message);
            }
        } catch (error) {
            console.error("RPC Error during nurse removal:", error);
        }

        // Close the panel regardless of success
        setSelectedNurse(null);
    }, [selectedDay, selectedShift]);


    // const addNurseToShift = useCallback((): void => {
    //     console.log(`ACTION: Adding a new nurse to ${selectedShift!.shiftName} shift on ${selectedDay!.dateString} (Mock)`);
    //     // Connect-ES mutation call here
    //     setSelectedNurse(null);
    // }, [selectedDay, selectedShift]);

    const addNurseToShift = useCallback((): void => {
        console.log(`ACTION: Adding a new nurse (mock). Would use RPC here.`);
        setSelectedNurse(null);
    }, []);


    // --- Side Effects & Lifecycle ---

    // Modal Fade-in and Scroll Lock
    useEffect(() => {
        const isDaySelected = !!selectedDay;
        document.body.style.overflow = isDaySelected ? 'hidden' : '';

        if (isDaySelected) {
            setTimeout(() => {
                setIsModalVisible(true);
            }, 0);
        } else {
            setIsModalVisible(false);
        }

        return () => {
            if (document.body.style.overflow === 'hidden') {
                document.body.style.overflow = '';
            }
        };
    }, [selectedDay]);

    // Escape Key Handler
    useEffect(() => {
        const handleEscapeKey = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                if (selectedNurse) {
                    closeNurseDetails();
                } else if (selectedDay) {
                    closeModal();
                }
            }
        };

        window.addEventListener('keydown', handleEscapeKey);
        return () => {
            window.removeEventListener('keydown', handleEscapeKey);
        };
    }, [selectedDay, selectedNurse, closeModal, closeNurseDetails]);


    return {
        currentDate,
        calendarDays,
        selectedDay,
        selectedShift,
        selectedNurse,
        isModalVisible,
        isTwoWeekView,
        toggleCalendarView,
        changeMonth,
        openShiftDetails,
        selectShift,
        openNurseDetails,
        closeNurseDetails,
        closeModal,
        removeNurseFromShift,
        addNurseToShift,
        SHIFT_NAMES,
    };
};