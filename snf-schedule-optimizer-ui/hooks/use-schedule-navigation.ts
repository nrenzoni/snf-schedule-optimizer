import { useCallback, useEffect, useMemo } from "react";
import { toast } from "sonner";
import {
  UICalendarDay,
  UIDraftState,
  UINurse,
  UISchedulerSettings,
  UIShift,
  ScheduleMap,
} from "@/types/scheduling";
import {
  formatDateYYYYMMDD,
  getStartOfMonth,
  getStartOfWeek,
  SHIFT_NAMES,
  getToday,
  getTodayString,
} from "@/lib/scheduling-logic";
import { parseAsBoolean, parseAsString, useQueryState } from "nuqs";
import { useScheduleCalendar } from "@/hooks/use-schedule-calendar";
import type { OrgFacility } from "@/gen/scheduling/v1/scheduling_pb";

export interface UseScheduleNavigationReturn {
  currentDate: Date;
  calendarDays: UICalendarDay[];
  currentViewAnchorDate: Date;
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
  stageShiftRemoval: (input: {
    employeeId: string;
    employeeName?: string | null;
    fromShiftId: string;
    shiftDate: string;
  }) => Promise<void>;
  addNurseToShift: () => void;
  clearDraft: () => void;
  updateSchedulerSettings: (settings: UISchedulerSettings) => void;
  SHIFT_NAMES: typeof SHIFT_NAMES;
}

interface UseScheduleNavigationProps {
  effectiveScheduleMap: ScheduleMap;
  isLoading: boolean;
  selectedFacility: OrgFacility | null;
  scheduleId: string | null;
  schedulerSettings: UISchedulerSettings;
  setSchedulerSettings: (settings: UISchedulerSettings) => void;
  draftState: UIDraftState;
  clearDraft: () => void;
  setHasPendingValidation: (value: boolean) => void;
  stageValidatedPatch: (input: {
    employeeId: string;
    employeeName?: string | null;
    fromShiftId: string | null;
    toShiftId: string | null;
    payPeriodStart: Date;
    successTitle: string;
    successDescription?: string;
  }) => Promise<boolean>;
}

export function useScheduleNavigation({
  effectiveScheduleMap,
  isLoading,
  selectedFacility,
  scheduleId,
  setSchedulerSettings,
  draftState,
  clearDraft,
  setHasPendingValidation,
  stageValidatedPatch,
}: UseScheduleNavigationProps): UseScheduleNavigationReturn {
  const [selectedDateStr, setSelectedDateStr] = useQueryState("date");
  const [isTwoWeekView, setIsTwoWeekView] = useQueryState(
    "isTwoWeek",
    parseAsBoolean.withDefault(true),
  );
  const [anchorDateStr, setAnchorDateStr] = useQueryState(
    "anchor",
    parseAsString.withDefault(getTodayString()),
  );
  const [selectedShiftId, setSelectedShiftId] = useQueryState("shift");
  const [selectedNurseId, setSelectedNurseId] = useQueryState("nurseId");

  const { calendarDays, currentViewAnchorDate } = useScheduleCalendar({
    effectiveScheduleMap,
    isLoading,
    anchorDateStr,
    isTwoWeekView,
  });

  const selectedDay = useMemo(() => {
    if (!selectedDateStr) return null;
    const schedule = effectiveScheduleMap.get(selectedDateStr) || null;
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
  }, [selectedDateStr, effectiveScheduleMap]);

  const selectedShift = useMemo(() => {
    if (!selectedDay?.schedule || !selectedShiftId) return null;
    return selectedDay.schedule.shifts.find((shift) => shift.shiftId === selectedShiftId) || null;
  }, [selectedDay, selectedShiftId]);

  const selectedNurse = useMemo(() => {
    if (!selectedShift || !selectedNurseId) return null;
    return selectedShift.nurses.find((nurse) => nurse.id === selectedNurseId) || null;
  }, [selectedShift, selectedNurseId]);

  const currentDate = useMemo(() => {
    return isTwoWeekView ? getToday() : currentViewAnchorDate;
  }, [isTwoWeekView, currentViewAnchorDate]);

  const closeModal = useCallback(() => {
    setSelectedDateStr(null);
    setSelectedShiftId(null);
    setSelectedNurseId(null);
  }, [setSelectedDateStr, setSelectedShiftId, setSelectedNurseId]);

  const toggleCalendarView = useCallback(async () => {
    const nextState = !isTwoWeekView;
    await setIsTwoWeekView(nextState);
    if (nextState) {
      setAnchorDateStr(formatDateYYYYMMDD(getToday()));
    } else {
      setAnchorDateStr(formatDateYYYYMMDD(getStartOfMonth(getToday())));
    }
  }, [isTwoWeekView, setAnchorDateStr, setIsTwoWeekView]);

  const changeMonth = useCallback(
    (offset: number) => {
      const newDate = new Date(
        currentViewAnchorDate.getFullYear(),
        currentViewAnchorDate.getMonth() + offset,
        1,
      );
      setAnchorDateStr(formatDateYYYYMMDD(newDate));
    },
    [currentViewAnchorDate, setAnchorDateStr],
  );

  const openShiftDetails = useCallback(
    (day: UICalendarDay) => {
      setSelectedDateStr(day.dateString);
      if (day.schedule?.shifts[0]) {
        setSelectedShiftId(day.schedule.shifts[0].shiftId);
      }
    },
    [setSelectedDateStr, setSelectedShiftId],
  );

  const selectShift = useCallback(
    (shift: UIShift) => {
      setSelectedShiftId(shift.shiftId);
      setSelectedNurseId(null);
    },
    [setSelectedShiftId, setSelectedNurseId],
  );

  const openNurseDetails = useCallback(
    (nurse: UINurse) => {
      setSelectedNurseId(nurse.id);
    },
    [setSelectedNurseId],
  );

  const removeNurseFromShift = useCallback(async (nurse: UINurse): Promise<void> => {
    if (!selectedShift) {
      toast.error("Shift removal unavailable", {
        description: "Select a nurse assignment before removing it.",
      });
      return;
    }

    await stageValidatedPatch({
      employeeId: nurse.id,
      employeeName: nurse.name,
      fromShiftId: selectedShift.shiftId,
      toShiftId: null,
      payPeriodStart: getStartOfWeek(
        selectedDay?.date ?? currentViewAnchorDate,
      ),
      successTitle: "Shift removal staged",
      successDescription: "Assignment removal will be applied with the next optimization run.",
    });
  }, [currentViewAnchorDate, selectedDay?.date, selectedShift, stageValidatedPatch]);

  const stageShiftRemoval = useCallback(
    async (input: {
      employeeId: string;
      employeeName?: string | null;
      fromShiftId: string;
      shiftDate: string;
    }) => {
      await stageValidatedPatch({
        employeeId: input.employeeId,
        employeeName: input.employeeName ?? null,
        fromShiftId: input.fromShiftId,
        toShiftId: null,
        payPeriodStart: getStartOfWeek(new Date(input.shiftDate)),
        successTitle: "Shift removal staged",
        successDescription: "Assignment removal will be applied with the next optimization run.",
      });
    },
    [stageValidatedPatch],
  );

  const addNurseToShift = useCallback((): void => {
    toast.error("Not yet available", {
      description: "Manual nurse-to-shift assignment will be available in a future update.",
    });
  }, []);

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
      if (event.key === "Escape" && selectedDay) {
        closeModal();
      }
    };

    window.addEventListener("keydown", handleEscapeKey);
    return () => {
      window.removeEventListener("keydown", handleEscapeKey);
    };
  }, [closeModal, selectedDay]);

  useEffect(() => {
    if (!selectedFacility || !scheduleId) {
      return;
    }
    if (draftState.hasPendingValidation) {
      setHasPendingValidation(false);
    }
  }, [draftState.hasPendingValidation, scheduleId, selectedFacility, setHasPendingValidation]);

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
    stageShiftRemoval,
    addNurseToShift,
    toggleCalendarView,
    clearDraft,
    updateSchedulerSettings,
    SHIFT_NAMES,
    currentViewAnchorDate,
  };
}
