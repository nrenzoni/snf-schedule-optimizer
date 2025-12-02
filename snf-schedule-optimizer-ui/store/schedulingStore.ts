import {create} from 'zustand';
import {formatDate, getStartOfMonth, getStartOfWeek, TODAY} from '@/utils/scheduling-logic';
import {ScheduleMap, UICalendarDay, UIDaySchedule, UINurse, UIShift} from '@/types/scheduling';

// --- Placeholder for Mock Hooks (replace with real API calls later) ---
// NOTE: In a real app, the data fetching logic would be integrated here or via middleware.
// For this refactor, we simulate the state management portion.

interface SchedulingState {
    // Data Loading & Source (Needed for setScheduleData logic)
    scheduleMap: ScheduleMap;
    isDataLoading: boolean;
    dataError: Error | null;

    // Calendar View State
    currentDate: Date;
    isTwoWeekView: boolean;
    isOptimized: boolean; // Tracks if optimized data is being displayed
    isOptimizing: boolean; // Optimization status (Spinner state)

    // Derived/Selected State
    calendarDays: UICalendarDay[];
    selectedDay: UICalendarDay | null;
    selectedShift: UIShift | null;
    selectedNurse: UINurse | null;

    // --- ACTIONS ---
    toggleCalendarView: () => void;
    changeMonth: (offset: number) => void;
    openShiftDetails: (day: UICalendarDay) => void;
    closeShiftModal: () => void;
    selectShift: (shift: UIShift) => void;
    openNurseDetails: (nurse: UINurse) => void;
    closeNurseDetails: () => void;
    setIsOptimizing: (status: boolean) => void;
    setIsOptimized: (status: boolean) => void;

    // 💡 MISSING DECLARATION ADDED:
    calculateCalendarDays: () => void;

    // Data Actions
    setScheduleData: (map: ScheduleMap, isLoading: boolean, error: Error | null) => void;
    removeNurseFromShift: (nurse: UINurse) => Promise<void>;
    addNurseToShift: () => void;
}

export const useSchedulingStore = create<SchedulingState>((set, get) => ({
    // --- Initial State ---
    scheduleMap: new Map(),
    isDataLoading: false,
    dataError: null,
    currentDate: getStartOfMonth(TODAY),
    isTwoWeekView: true,
    isOptimized: false,
    calendarDays: [],
    selectedDay: null,
    selectedShift: null,
    selectedNurse: null,
    isOptimizing: false,

    // --- Core Actions ---

    setScheduleData: (map, isLoading, error) => {
        set({
            scheduleMap: map,
            isDataLoading: isLoading,
            dataError: error
        });
        get().calculateCalendarDays()
    },

    setIsOptimized: (status) => set({
        isOptimized: status
    }),

    setIsOptimizing: (status) => set({isOptimizing: status}), // Fix for optimization spinner state

    toggleCalendarView: () => {
        set(state => {
            const newIsTwoWeekView = !state.isTwoWeekView;
            // When switching to 2-week view, we anchor the header to TODAY's month.
            const newCurrentDate = newIsTwoWeekView ? TODAY : getStartOfMonth(TODAY);

            return {
                isTwoWeekView: newIsTwoWeekView,
                currentDate: newCurrentDate
            };
        });
        get().calculateCalendarDays();
    },

    changeMonth: (offset) => {
        set(state => {
            const newDate = new Date(state.currentDate.getFullYear(), state.currentDate.getMonth() + offset, 1);
            return {currentDate: newDate};
        });
        get().calculateCalendarDays();
    },

    openShiftDetails: (day) => set({
        selectedDay: day,
        selectedShift: day.schedule?.shifts?.[0] || null,
    }),

    closeShiftModal: () => set({selectedDay: null, selectedShift: null, selectedNurse: null}),

    selectShift: (shift) => set({selectedShift: shift, selectedNurse: null}),

    openNurseDetails: (nurse) => set({selectedNurse: nurse}),
    closeNurseDetails: () => set({selectedNurse: null}),

    calculateCalendarDays: () => {
        console.log("Calculating calendar days...");

        const {currentDate, isTwoWeekView, scheduleMap} = get();

        const startDate = isTwoWeekView
            ? getStartOfWeek(TODAY)
            : (() => {
                const year = currentDate.getFullYear();
                const month = currentDate.getMonth();
                const firstDayOfMonth = new Date(year, month, 1);
                const startOffset = firstDayOfMonth.getDay();
                return new Date(year, month, 1 - startOffset);
            })();

        const days: UICalendarDay[] = [];
        const todayStart = new Date(TODAY);
        todayStart.setHours(0, 0, 0, 0);
        const todayStartMs = todayStart.getTime();

        // Calculate window end date for comparison
        const windowEnd = new Date(TODAY);
        windowEnd.setDate(TODAY.getDate() + 13);
        const windowEndMs = windowEnd.getTime();

        const totalDaysToRender = isTwoWeekView ? 14 : 42;
        const contextMonth = currentDate.getMonth();

        const mutableDate = new Date(startDate);
        mutableDate.setHours(0, 0, 0, 0);

        for (let i = 0; i < totalDaysToRender; i++) {
            const dayDate = new Date(mutableDate);
            const dayDateString = formatDate(dayDate);
            const schedule: UIDaySchedule | null = scheduleMap.get(dayDateString) || null;
            const dayDateMs = dayDate.getTime();

            let totalRequiredHours = 0;
            let totalActualHours = 0;
            let dayHPRDPercentage = 0;

            if (schedule) {
                totalRequiredHours = schedule.shifts.reduce((sum, s) => sum + s.requiredHours, 0);
                totalActualHours = schedule.shifts.reduce((sum, s) => sum + s.actualHours, 0);

                if (totalRequiredHours > 0) {
                    dayHPRDPercentage = Math.min(100, (totalActualHours / totalRequiredHours) * 100);
                }
            }

            const isWithinWindow = dayDateMs >= todayStartMs && dayDateMs <= windowEndMs;

            const isSelectable = isTwoWeekView
                ? isWithinWindow
                : dayDate.getMonth() === contextMonth && isWithinWindow;

            days.push({
                coverage: 0,
                isPadding: false,
                date: dayDate,
                dateString: dayDateString,
                dayOfMonth: dayDate.getDate(),
                isToday: dayDateString === formatDate(TODAY),
                isCurrentMonth: !isTwoWeekView && dayDate.getMonth() === contextMonth,
                isSelectable: isSelectable,
                schedule,
                dayHPRDPercentage: dayHPRDPercentage
            });

            mutableDate.setDate(mutableDate.getDate() + 1); // Increment for the next day
        }

        set({calendarDays: days});
    },

    // --- Mock Mutation Handlers ---
    removeNurseFromShift: async (nurse) => {
        console.log(`RPC: Removing ${nurse.name}. (Mock)`);
        get().closeNurseDetails();
    },

    addNurseToShift: () => {
        console.log("RPC: Adding available nurse. (Mock)");
        get().closeNurseDetails();
    },
}));