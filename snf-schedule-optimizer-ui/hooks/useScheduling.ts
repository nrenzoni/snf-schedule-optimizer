import {useState, useMemo, useCallback, useEffect} from 'react';
import {CalendarDay, Shift, Nurse, DaySchedule} from '@/types/scheduling';
import {
    getStartOfMonth, TODAY, TODAY_STRING, FOURTEEN_DAYS_AHEAD,
    generateMockScheduleMap, formatDate, SHIFT_NAMES
} from '@/utils/scheduling-logic';
import {schedulingClient} from "@/api/scheduling-client";
import {GetMonthlyScheduleResponse} from "@/gen/schema/scheduling_pb";

// Structure for the received schedules (Map from YYYY-MM-DD string to DaySchedule)
type ScheduleMap = Map<string, DaySchedule>;


export const useScheduling = () => {
    // --- State Hooks ---
    const [currentDate, setCurrentDate] = useState(getStartOfMonth(TODAY));
    const [selectedDay, setSelectedDay] = useState<CalendarDay | null>(null);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [selectedShift, setSelectedShift] = useState<Shift | null>(null);
    const [selectedNurse, setSelectedNurse] = useState<Nurse | null>(null);
    const [isTwoWeekView, setIsTwoWeekView] = useState(false);

    const [schedules, setSchedules] = useState<ScheduleMap>(new Map());
    const [isLoading, setIsLoading] = useState(false);

    // --- Data Fetching Logic (Connect-ES) ---

    const fetchSchedule = useCallback(async (date: Date) => {
        const startDateString = formatDate(getStartOfMonth(date));
        setIsLoading(true);
        console.log(`Fetching schedule for month starting: ${startDateString}`);

        try {
            // 1. Call the Connect-ES client
            // Note: We use the generated protobuf types for the request/response here.
            const request = {startDate: startDateString};
            const response = await schedulingClient.getMonthlySchedule(request);

            // 2. Process the response map
            const newSchedules = new Map<string, DaySchedule>();
            Object.entries(response.schedules).forEach(([dateStr, schedule]) => {
                newSchedules.set(dateStr, schedule);
            });

            setSchedules(newSchedules);
            console.log(`Successfully fetched ${newSchedules.size} days of schedules.`);

        } catch (error) {
            console.error("RPC Error fetching schedule:", error);
            // Fallback: If the fetch fails, ensure the schedules are cleared
            setSchedules(new Map());
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Effect to trigger schedule fetch when the month changes
    useEffect(() => {
        fetchSchedule(currentDate);
    }, [currentDate, fetchSchedule]);


    // 1. Memoized schedule map generated based on the current month
    // const mockScheduleMap = useMemo(() => {
    //     return generateMockScheduleMap(currentDate);
    // }, [currentDate]);
    const mockScheduleMap = useMemo(() => {
        // We now return the fetched schedules
        return schedules;
    }, [schedules]);


    // 2. Computed calendar days array for the grid
    const calendarDays = useMemo<CalendarDay[]>(() => {
        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();

        const firstDayOfMonth = new Date(year, month, 1);
        const startOffset = firstDayOfMonth.getDay();
        const startDate = new Date(year, month, 1 - startOffset);

        const days: CalendarDay[] = [];
        const todayStart = new Date(TODAY);
        todayStart.setHours(0, 0, 0, 0);
        const todayStartMs = todayStart.getTime();
        const windowEndMs = FOURTEEN_DAYS_AHEAD.getTime();
        const totalDaysToRender = isTwoWeekView ? 14 : 42;

        for (let i = 0; i < totalDaysToRender; i++) {
            const dayDate = new Date(startDate);
            dayDate.setDate(startDate.getDate() + i);

            const dayDateString = formatDate(dayDate);
            const schedule = mockScheduleMap.get(dayDateString) || null;
            const dayDateMs = dayDate.getTime();

            let isDayHRPDMet = false;
            let dayHRPDPercentage = 0;

            if (schedule) {
                isDayHRPDMet = schedule.shifts.every(s => s.isHRPDMet);
                const totalRequiredHours = schedule.shifts.reduce((sum, s) => sum + s.requiredHours, 0);
                const totalActualHours = schedule.shifts.reduce((sum, s) => sum + s.actualHours, 0);

                if (totalRequiredHours > 0) {
                    dayHRPDPercentage = Math.min(100, (totalActualHours / totalRequiredHours) * 100);
                }
            }

            const isWithinWindow = dayDateMs >= todayStartMs && dayDateMs <= windowEndMs;
            const isSelectable = dayDate.getMonth() === month && isWithinWindow;

            days.push({
                date: dayDate,
                dateString: dayDateString,
                dayOfMonth: dayDate.getDate(),
                isToday: dayDateString === TODAY_STRING,
                isCurrentMonth: dayDate.getMonth() === month,
                isSelectable: isSelectable,
                schedule,
                isDayHRPDMet,
                dayHRPDPercentage,
            });
        }
        return days;
    }, [currentDate, mockScheduleMap, isTwoWeekView]);

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
        // When switching to month view, reset to the current month's start date
        if (!isTwoWeekView) {
            setCurrentDate(getStartOfMonth(TODAY));
        }
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
        setSelectedShift(day.schedule.shifts[0]); // Default to first shift
        setSelectedNurse(null);
    }, []);

    const selectShift = useCallback((shift: Shift): void => {
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