import { useCallback, useEffect, useMemo } from "react";
import { toast } from "sonner";
import {
  UICalendarDay,
  UIDaySchedule,
  UINurse,
  UISchedulerSettings,
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
import {
  defaultSchedulerSettings,
  useSchedulingStore,
} from "@/store/schedulingStore";
import { useShallow } from "zustand/react/shallow";
import { parseAsBoolean, parseAsString, useQueryState } from "nuqs";
import {
  DaySchedule as ProtoDaySchedule,
  FinancialReport,
  OptimizationSettings,
  OptimizationStats,
  OptimizationSummary,
} from "@/gen/scheduling/v1/scheduling_pb";
import {
  protoDayToUI,
  protoFinancialsToUI,
  protoStatsToUI,
  protoSummaryToUI,
} from "@/hooks/use-schedule-query";

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
  triggerOptimization: () => Promise<void>;
  updateSchedulerSettings: (settings: UISchedulerSettings) => void;
  SHIFT_NAMES: typeof SHIFT_NAMES;
}

const optimizationSettingsToProto = (settings: UISchedulerSettings): OptimizationSettings => ({
  $typeName: "scheduling.v1.OptimizationSettings",
  useMlForecast: settings.useMLForecast,
  useCalloutBuffer: settings.useCalloutBuffer,
  bufferThreshold: settings.bufferThreshold,
  minRestPeriod: settings.minRestPeriod,
  maxShiftLength: settings.maxShiftLength,
  premiumWeekend: settings.premiumWeekend,
  premiumHoliday: settings.premiumHoliday,
  overtimeAvoidancePenalty: settings.overtimeAvoidancePenalty,
  teamConsistencyPenalty: settings.teamConsistencyPenalty,
  highRiskShiftPenalty: settings.highRiskShiftPenalty,
  customPreferencePenalty: settings.customPreferencePenalty,
});

export function useScheduling(): UseSchedulingReturn {
  const {
    scheduleMap,
    isLoading,
    setIsOptimizing,
    schedulerSettings,
    setSchedulerSettings,
    selectedFacility,
    setOptimizeResult,
  } = useSchedulingStore(
    useShallow((state) => ({
      scheduleMap: state.scheduleMap,
      isLoading: state.isDataLoading,
      setIsOptimizing: state.setIsOptimizing,
      schedulerSettings: state.schedulerSettings,
      setSchedulerSettings: state.setSchedulerSettings,
      selectedFacility: state.selectedFacility,
      setOptimizeResult: state.setOptimizeResult,
    })),
  );

  const [selectedDateStr, setSelectedDateStr] = useQueryState("date");
  const [isTwoWeekView, setIsTwoWeekView] = useQueryState(
    "isTwoWeek",
    parseAsBoolean.withDefault(true),
  );
  const [anchorDateStr, setAnchorDateStr] = useQueryState(
    "anchor",
    parseAsString.withDefault(TODAY_STRING),
  );
  const [selectedShiftName, setSelectedShiftName] = useQueryState("shift");
  const [selectedNurseId, setSelectedNurseId] = useQueryState("nurseId");

  const currentViewAnchorDate = useMemo(() => new Date(anchorDateStr), [anchorDateStr]);

  const triggerOptimization = useCallback(async () => {
    if (!selectedFacility) {
      toast.error("Optimization unavailable", {
        description: "No facility context is loaded yet.",
      });
      return;
    }

    const startDate = new Date(currentViewAnchorDate);
    startDate.setDate(startDate.getDate() - 2);
    const endDate = new Date(startDate);
    endDate.setDate(endDate.getDate() + 5);

    try {
      setIsOptimizing(true);
      const response = await schedulingClient.optimizeSchedule({
        orgId: selectedFacility.orgId,
        facilityId: selectedFacility.facilityId,
        startDate: formatDateYYYMMDD(startDate),
        endDate: formatDateYYYMMDD(endDate),
        settings: optimizationSettingsToProto(schedulerSettings),
        persistResult: true,
      });

      if (!response.isSuccess) {
        toast.error("Optimization failed", {
          description: response.errorDetails || "The optimizer did not return a schedule.",
        });
        setIsOptimizing(false);
        return;
      }

      const optimizedMap = new Map<string, UIDaySchedule>();
      Object.entries(response.schedules).forEach(([date, day]) => {
        optimizedMap.set(date, protoDayToUI(day as ProtoDaySchedule));
      });

      const summary = protoSummaryToUI(response.summary as OptimizationSummary | undefined);
      const stats = protoStatsToUI(response.stats as OptimizationStats | undefined);
      const financials = protoFinancialsToUI(response.financials as FinancialReport | undefined);

      setOptimizeResult(
        optimizedMap,
        selectedFacility,
        response.scheduleId,
        response.scheduleVersion,
        summary,
        stats,
        financials,
      );

      toast.success("Optimization completed", {
        description: stats
          ? `${Math.round(stats.executionTimeMs)} ms, $${Math.round(financials?.totalEnterpriseCost ?? 0).toLocaleString()} projected labor cost`
          : "Schedule updated successfully.",
      });
    } catch (error) {
      toast.error("Optimization failed", {
        description: error instanceof Error ? error.message : "Unexpected optimizer error",
      });
      setIsOptimizing(false);
    }
  }, [
    currentViewAnchorDate,
    schedulerSettings,
    selectedFacility,
    setIsOptimizing,
    setOptimizeResult,
  ]);

  const selectedDay = useMemo(() => {
    if (!selectedDateStr) return null;
    const schedule = scheduleMap.get(selectedDateStr) || null;
    return {
      dateString: selectedDateStr,
      date: new Date(selectedDateStr),
      schedule,
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
    return selectedDay.schedule.shifts.find((shift) => shift.shiftName === selectedShiftName) || null;
  }, [selectedDay, selectedShiftName]);

  const selectedNurse = useMemo(() => {
    if (!selectedShift || !selectedNurseId) return null;
    return selectedShift.nurses.find((nurse) => nurse.id === selectedNurseId) || null;
  }, [selectedShift, selectedNurseId]);

  const currentDate = useMemo(() => {
    return isTwoWeekView ? TODAY : currentViewAnchorDate;
  }, [isTwoWeekView, currentViewAnchorDate]);

  const calendarDays = useMemo<UICalendarDay[]>(() => {
    if (isLoading) {
      return [];
    }

    const startDate = isTwoWeekView
      ? getStartOfWeek(TODAY)
      : (() => {
          const year = currentViewAnchorDate.getFullYear();
          const month = currentViewAnchorDate.getMonth();
          const firstDayOfMonth = new Date(year, month, 1);
          const startOffset = firstDayOfMonth.getDay();
          return new Date(year, month, 1 - startOffset);
        })();

    const iterationDay = new Date(startDate);
    const days: UICalendarDay[] = [];
    const todayStart = new Date(TODAY);
    todayStart.setHours(0, 0, 0, 0);
    const todayStartMs = todayStart.getTime();
    const windowEndMs = FOURTEEN_DAYS_AHEAD.getTime();
    const totalDaysToRender = isTwoWeekView ? 14 : 42;
    const contextMonth = currentViewAnchorDate.getMonth();

    for (let i = 0; i < totalDaysToRender; i++) {
      const dayDate = new Date(iterationDay);
      const dayDateString = formatDateYYYMMDD(dayDate);
      const schedule = scheduleMap.get(dayDateString) || null;
      const dayDateMs = dayDate.getTime();

      let dayHPRDPercentage = 0;
      if (schedule) {
        const totalRequiredHours = schedule.shifts.reduce((sum, shift) => sum + shift.requiredHours, 0);
        const totalActualHours = schedule.shifts.reduce((sum, shift) => sum + shift.actualHours, 0);
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
        isToday: dayDateString === TODAY_STRING,
        isCurrentMonth: !isTwoWeekView && dayDate.getMonth() === contextMonth,
        isSelectable,
        schedule,
        dayHPRDPercentage,
      });

      iterationDay.setDate(iterationDay.getDate() + 1);
    }
    return days;
  }, [currentViewAnchorDate, scheduleMap, isTwoWeekView, isLoading]);

  const closeModal = useCallback(() => {
    setSelectedDateStr(null);
    setSelectedShiftName(null);
    setSelectedNurseId(null);
  }, [setSelectedDateStr, setSelectedShiftName, setSelectedNurseId]);

  const toggleCalendarView = useCallback(async () => {
    const nextState = !isTwoWeekView;
    await setIsTwoWeekView(nextState);
    if (nextState) {
      setAnchorDateStr(formatDateYYYMMDD(TODAY));
    } else {
      setAnchorDateStr(formatDateYYYMMDD(getStartOfMonth(TODAY)));
    }
  }, [isTwoWeekView, setAnchorDateStr, setIsTwoWeekView]);

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

  const removeNurseFromShift = useCallback(
    async (nurse: UINurse): Promise<void> => {
      if (!selectedDay || !selectedShift) return;

      const request = {
        shiftDate: selectedDay.dateString,
        shiftName: selectedShift.shiftName,
        nurseId: nurse.id,
      };

      try {
        const response = await schedulingClient.removeNurseFromShift(request);

        if (!response.success) {
          console.error("Failed to remove nurse:", response.message);
        }
      } catch (error) {
        console.error("RPC Error during nurse removal:", error);
      }
    },
    [selectedDay, selectedShift],
  );

  const addNurseToShift = useCallback((): void => {}, []);

  const closeNurseDetails = useCallback(() => {
    setSelectedNurseId(null);
  }, [setSelectedNurseId]);

  const updateSchedulerSettings = useCallback(
    (settings: UISchedulerSettings) => {
      setSchedulerSettings(settings);
    },
    [setSchedulerSettings],
  );

  useEffect(() => {
    const isDaySelected = !!selectedDay;
    document.body.style.overflow = isDaySelected ? "hidden" : "";
    return () => {
      if (document.body.style.overflow === "hidden") {
        document.body.style.overflow = "";
      }
    };
  }, [selectedDay]);

  useEffect(() => {
    const handleEscapeKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (selectedDay) {
          closeModal();
        }
      }
    };

    window.addEventListener("keydown", handleEscapeKey);
    return () => {
      window.removeEventListener("keydown", handleEscapeKey);
    };
  }, [closeModal, selectedDay]);

  return {
    selectedDay,
    selectedShift,
    selectedNurse,
    isModalVisible: !!selectedDay,
    openShiftDetails,
    closeModal,
    selectShift,
    openNurseDetails,
    closeNurseDetails,
    changeMonth,
    currentDate,
    calendarDays,
    isTwoWeekView,
    removeNurseFromShift,
    addNurseToShift,
    toggleCalendarView,
    triggerOptimization,
    updateSchedulerSettings,
    SHIFT_NAMES,
  };
}

export { defaultSchedulerSettings };
