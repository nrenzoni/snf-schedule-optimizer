import { useCallback, useEffect, useMemo, useState } from "react";
import {
  UICalendarDay,
  UIDaySchedule as UIDaySchedule,
  UINurse,
  UIShift,
} from "@/types/scheduling";
import {
  formatDateYYYMMDD,
  FOURTEEN_DAYS_AHEAD,
  getStartOfMonth,
  getStartOfWeek,
  SHIFT_NAMES,
  TODAY,
  TODAY_STRING,
} from "@/utils/scheduling-logic";
import { schedulingClient } from "@/api/scheduling-client";
import { useSchedulingStore } from "@/store/schedulingStore";
import { useShallow } from "zustand/react/shallow";
import { parseAsBoolean, parseAsString, useQueryState } from "nuqs";

interface UseSchedulingReturn {
  currentDate: Date;
  calendarDays: UICalendarDay[];
  selectedDay: UICalendarDay | null;
  selectedShift: UIShift | null;
  selectedNurse: UINurse | null;
  isModalVisible: boolean;
  isTwoWeekView: boolean;
  toggleCalendarView: () => void;
  changeMonth: (offset: number) => void;
  openShiftDetails: (day: UICalendarDay) => void;
  selectShift: (shift: UIShift) => void;
  openNurseDetails: (nurse: UINurse) => void;
  closeNurseDetails: () => void;
  closeModal: () => void;
  removeNurseFromShift: (nurse: UINurse) => Promise<void>;
  addNurseToShift: () => void;
  triggerOptimization: () => void;
  SHIFT_NAMES: typeof SHIFT_NAMES;
}

export function useScheduling(optimizationCount: number): UseSchedulingReturn {
  const { scheduleMap, isLoading, setIsOptimized, setIsOptimizing } =
    useSchedulingStore(
      useShallow((state) => ({
        scheduleMap: state.scheduleMap, // This is populated by useScheduleQuery elsewhere
        isLoading: state.isDataLoading,
        setIsOptimized: state.setIsOptimized,
        setIsOptimizing: state.setIsOptimizing,
      })),
    );

  // Tracks which day is open: ?date=2023-10-05
  const [selectedDateStr, setSelectedDateStr] = useQueryState("date");

  const [isTwoWeekView, setIsTwoWeekView] = useQueryState(
    "isTwoWeek",
    parseAsBoolean.withDefault(true),
  );

  const [anchorDateStr, setAnchorDateStr] = useQueryState(
    "anchor",
    parseAsString.withDefault(TODAY_STRING),
  );

  // Tracks specific shift/nurse selection
  const [selectedShiftName, setSelectedShiftName] = useQueryState("shift");
  const [selectedNurseId, setSelectedNurseId] = useQueryState("nurseId");

  const triggerOptimization = useCallback(() => {
    setIsOptimizing(true);
    setIsOptimized(false);
    setTimeout(() => setIsOptimized(true), 0);
  }, [setIsOptimized, setIsOptimizing]);

  const [startOfWeek, setStartOfWeek] = useState(getStartOfWeek(TODAY));
  const [isModalVisible, setIsModalVisible] = useState(false);

  const currentViewAnchorDate = useMemo(
    () => new Date(anchorDateStr),
    [anchorDateStr],
  );

  const selectedDay = useMemo(() => {
    if (!selectedDateStr) return null;
    const schedule = scheduleMap.get(selectedDateStr) || null;
    // Reconstruct minimal Day object needed for modal
    return {
      dateString: selectedDateStr,
      date: new Date(selectedDateStr),
      schedule,
      // ... add other necessary dummy props if needed for types
      isToday: false,
      coverage: 0,
      isPadding: false,
      dayOfMonth: 1,
      isCurrentMonth: true,
      isSelectable: true,
      dayHPRDPercentage: 0,
    } as UICalendarDay;
  }, [selectedDateStr, scheduleMap]);

  const selectedShift = useMemo(() => {
    if (!selectedDay?.schedule || !selectedShiftName) return null;
    return (
      selectedDay.schedule.shifts.find(
        (s) => s.shiftName === selectedShiftName,
      ) || null
    );
  }, [selectedDay, selectedShiftName]);

  const selectedNurse = useMemo(() => {
    if (!selectedShift || !selectedNurseId) return null;
    return selectedShift.nurses.find((n) => n.id === selectedNurseId) || null;
  }, [selectedShift, selectedNurseId]);

  // --- Data Fetching Logic (moved to useSchedules) ---
  // const { schedules, isLoading, fetchSchedule } = useSchedules(currentDate);
  // const { schedules, isLoading, fetchSchedule, triggerOptimization } =
  //   useMockScheduling(currentViewAnchorDate, optimizationCount);

  const currentDate = useMemo(() => {
    return isTwoWeekView ? TODAY : currentViewAnchorDate;
  }, [isTwoWeekView, currentViewAnchorDate]);

  // 2. Computed calendar days array for the grid
  // Determine the *actual* starting date for the calendar grid display.
  // If it's a 2-week view, start from the `currentDate` (which is the start of the week).
  // If it's a full month view, calculate the first Sunday of the month's grid.
  const calendarDays = useMemo<UICalendarDay[]>(() => {
    // Guard Clause: Do not render calendar days until loading is explicitly complete.
    if (isLoading) {
      return [];
    }

    // Determine the *actual* starting date for the calendar grid display.
    // If it's a 2-week view, start from the `currentDate` (which is the start of the week).
    // If it's a full month view, calculate the first Sunday of the month's grid.
    const startDate = isTwoWeekView
      ? getStartOfWeek(TODAY)
      : // 💡 If month view, calculate the start of the grid based on the ANCHOR DATE (Dec 1st).
        (() => {
          const year = currentViewAnchorDate.getFullYear();
          const month = currentViewAnchorDate.getMonth();
          const firstDayOfMonth = new Date(year, month, 1);
          const startOffset = firstDayOfMonth.getDay();
          return new Date(year, month, 1 - startOffset);
        })();

    // Make a mutable copy of the START DATE for iteration
    const iterationDay = new Date(startDate);
    const days: UICalendarDay[] = [];
    const todayStart = new Date(TODAY);
    todayStart.setHours(0, 0, 0, 0);
    const todayStartMs = todayStart.getTime();
    const windowEndMs = FOURTEEN_DAYS_AHEAD.getTime();
    const totalDaysToRender = isTwoWeekView ? 14 : 42;

    // We no longer need the 'year' and 'month' variables from the currentDate for determining
    // `isCurrentMonth` since we want the 2-week view to not be constrained by the month.
    // However, we need to pass a context month for `isSelectable` logic if we want to keep it.
    const contextMonth = startOfWeek.getMonth();

    for (let i = 0; i < totalDaysToRender; i++) {
      const dayDate = new Date(iterationDay);
      // dayDate.setDate(startDate.getDate() + i);

      const dayDateString = formatDateYYYMMDD(dayDate);

      // READ DIRECTLY FROM STORE MAP
      const schedule: UIDaySchedule | null =
        scheduleMap.get(dayDateString) || null;
      const dayDateMs = dayDate.getTime();

      let dayHPRDPercentage = 0;

      if (schedule) {
        const totalRequiredHours = schedule.shifts.reduce(
          (sum, s) => sum + s.requiredHours,
          0,
        );
        const totalActualHours = schedule.shifts.reduce(
          (sum, s) => sum + s.actualHours,
          0,
        );
        if (totalRequiredHours > 0) {
          dayHPRDPercentage = Math.min(
            100,
            (totalActualHours / totalRequiredHours) * 100,
          );
        }
      }

      const isWithinWindow =
        dayDateMs >= todayStartMs && dayDateMs <= windowEndMs;

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
        dayHPRDPercentage: dayHPRDPercentage,
      });

      iterationDay.setDate(iterationDay.getDate() + 1);
    }
    console.log(
      `Generated ${totalDaysToRender}-day calendar grid starting from ${formatDateYYYMMDD(startDate)}`,
    );
    return days;
  }, [startOfWeek, scheduleMap, isTwoWeekView, isLoading]);

  // --- Utility Functions ---

  // const closeModalImmediately = useCallback(() => {
  //   setSelectedDay(null);
  //   setSelectedShift(null);
  //   setSelectedNurse(null);
  // }, []);

  // const closeModal = useCallback(() => {
  //   setIsModalVisible(false);
  //   setTimeout(() => {
  //     closeModalImmediately();
  //   }, 300); // Wait for modal fade transition
  // }, [closeModalImmediately]);

  const closeModal = useCallback(() => {
    // Clear URL params to close modal
    setSelectedDateStr(null);
    setSelectedShiftName(null);
    setSelectedNurseId(null);
  }, [setSelectedDateStr, setSelectedShiftName, setSelectedNurseId]);

  // --- Event Handlers ---

  const toggleCalendarView = useCallback(async () => {
    const nextState = !isTwoWeekView;

    // Await the first URL push
    await setIsTwoWeekView(nextState);

    // When switching TO month view, reset to the current month's start date
    if (nextState) {
      setAnchorDateStr(formatDateYYYMMDD(getStartOfMonth(TODAY)));
    }
    // When switching TO 2-week view, reset to the current week's start date (Sunday)
    else {
      setAnchorDateStr(formatDateYYYMMDD(TODAY));
    }
    // NOTE: Must include getStartOfWeek in the dependency array or define it outside
    // the component or inside with useCallback/useMemo. Since it's a simple helper,
    // defining it outside the hook is cleaner.
  }, [isTwoWeekView, setIsTwoWeekView, setAnchorDateStr]);

  const changeMonth = useCallback(
    (offset: number) => {
      const newDate = new Date(
        currentViewAnchorDate.getFullYear(),
        currentViewAnchorDate.getMonth() + offset,
        1,
      );
      setAnchorDateStr(formatDateYYYMMDD(newDate));
    },
    [currentViewAnchorDate, setAnchorDateStr],
  );

  const openShiftDetails = useCallback(
    (day: UICalendarDay) => {
      // URL Update: ?date=2023-10-05&shift=Morning
      setSelectedDateStr(day.dateString);
      if (day.schedule?.shifts[0]) {
        setSelectedShiftName(day.schedule.shifts[0].shiftName);
      }
    },
    [setSelectedDateStr, setSelectedShiftName],
  );

  const selectShift = useCallback(
    (shift: UIShift) => {
      setSelectedShiftName(shift.shiftName);
      setSelectedNurseId(null);
    },
    [setSelectedShiftName, setSelectedNurseId],
  );

  const openNurseDetails = useCallback(
    (nurse: UINurse) => {
      setSelectedNurseId(nurse.id);
    },
    [setSelectedNurseId],
  );

  // --- Connect-ES Mutation Action ---

  // const removeNurseFromShift = useCallback((nurse: Nurse): void => {
  //     console.log(`ACTION: Removing ${nurse.name} from ${selectedShift!.shiftName} shift on ${selectedDay!.dateString}`);
  //     // In a real app, this would trigger a Connect-ES mutation call.
  //     setSelectedNurse(null);
  // }, [selectedDay, selectedShift]);

  const removeNurseFromShift = useCallback(
    async (nurse: UINurse): Promise<void> => {
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
      // setSelectedNurse(null);
    },
    [selectedDay, selectedShift],
  );

  // const addNurseToShift = useCallback((): void => {
  //     console.log(`ACTION: Adding a new nurse to ${selectedShift!.shiftName} shift on ${selectedDay!.dateString} (Mock)`);
  //     // Connect-ES mutation call here
  //     setSelectedNurse(null);
  // }, [selectedDay, selectedShift]);

  const addNurseToShift = useCallback((): void => {
    console.log(`ACTION: Adding a new nurse (mock). Would use RPC here.`);
    // setSelectedNurse(null);
  }, []);

  const closeNurseDetails = useCallback(() => {
    // Setting this to null removes ?nurseId=... from the URL
    setSelectedNurseId(null);
  }, [setSelectedNurseId]);

  // --- Side Effects & Lifecycle ---

  // Modal Fade-in and Scroll Lock
  useEffect(() => {
    console.log("useEffect: selectedDay changed:", selectedDay);
    const isDaySelected = !!selectedDay;
    document.body.style.overflow = isDaySelected ? "hidden" : "";

    if (isDaySelected) {
      setTimeout(() => {
        setIsModalVisible(true);
      }, 0);
    } else {
      setIsModalVisible(false);
    }

    return () => {
      if (document.body.style.overflow === "hidden") {
        document.body.style.overflow = "";
      }
    };
  }, [selectedDay]);

  // Escape Key Handler
  useEffect(() => {
    console.log("useEffect: Setting up Escape key handler.");
    const handleEscapeKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (selectedNurse) {
          // closeNurseDetails();
        } else if (selectedDay) {
          closeModal();
        }
      }
    };

    window.addEventListener("keydown", handleEscapeKey);
    return () => {
      window.removeEventListener("keydown", handleEscapeKey);
    };
  }, [selectedDay, selectedNurse, closeModal]);

  return {
    // State (Derived from URL)
    // currentDate,
    // calendarDays,
    selectedDay,
    selectedShift,
    selectedNurse,
    isModalVisible: !!selectedDay, // Modal is open if date param exists

    // selectedDay,
    // selectedShift,
    // selectedNurse,
    // isModalVisible,

    // Actions (Updates URL)
    openShiftDetails,
    closeModal,
    selectShift,
    openNurseDetails,
    closeNurseDetails,

    changeMonth,
    // openShiftDetails,
    // selectShift,
    // openNurseDetails,

    currentDate,
    calendarDays,
    isTwoWeekView,
    removeNurseFromShift,
    addNurseToShift,
    toggleCalendarView,
    triggerOptimization,
    SHIFT_NAMES,
  };
}
