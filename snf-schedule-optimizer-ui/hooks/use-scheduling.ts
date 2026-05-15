import { useCallback, useEffect, useMemo } from "react";
import { toast } from "sonner";
import {
  UICalendarDay,
  UINurse,
  UIPatchConflict,
  UISchedulerSettings,
  UIShift,
} from "@/types/scheduling";
import {
  formatDateYYYYMMDD,
  getStartOfMonth,
  getStartOfWeek,
  SHIFT_NAMES,
  TODAY,
  TODAY_STRING,
} from "@/utils/scheduling-logic";
import {
  getScheduleStatus,
  hasBlockingConflicts,
  startOptimizationRun,
} from "@/api/scheduling-client";
import {
  defaultSchedulerSettings,
  useSchedulingStore,
} from "@/store/schedulingStore";
import { useShallow } from "zustand/react/shallow";
import { parseAsBoolean, parseAsString, useQueryState } from "nuqs";
import { OptimizationSettings } from "@/gen/scheduling/v1/scheduling_pb";
import {
  protoOptimizationRunToUI,
  protoPatchConflictToUI,
} from "@/lib/proto-mappers";
import { isRunActive, toProtoPatch } from "@/lib/scheduling-helpers";
import { createClientUuid } from "@/lib/utils";
import { useStagedScheduleActions } from "@/hooks/use-staged-schedule-actions";
import { useScheduleCalendar } from "@/hooks/use-schedule-calendar";

interface UseSchedulingReturn {
  currentDate: Date;
  calendarDays: UICalendarDay[];
  selectedDay: UICalendarDay | null;
  selectedShift: UIShift | null;
  selectedNurse: UINurse | null;
  isModalVisible: boolean;
  isTwoWeekView: boolean;
  isRunActive: boolean;
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
  triggerOptimization: (allowOverwrite?: boolean) => Promise<void>;
  clearDraft: () => void;
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
    effectiveScheduleMap,
    isLoading,
    schedulerSettings,
    setSchedulerSettings,
    selectedFacility,
    scheduleId,
    scheduleVersion,
    draftState,
    activeRun,
    setDraftConflicts,
    setHasPendingValidation,
    setActiveRun,
    setHasNewerVersion,
    clearDraft,
  } = useSchedulingStore(
    useShallow((state) => ({
      effectiveScheduleMap: state.effectiveScheduleMap,
      isLoading: state.isDataLoading,
      schedulerSettings: state.schedulerSettings,
      setSchedulerSettings: state.setSchedulerSettings,
      selectedFacility: state.selectedFacility,
      scheduleId: state.scheduleId,
      scheduleVersion: state.scheduleVersion,
      draftState: state.draftState,
      activeRun: state.activeRun,
      setDraftConflicts: state.setDraftConflicts,
      setHasPendingValidation: state.setHasPendingValidation,
      setActiveRun: state.setActiveRun,
      setHasNewerVersion: state.setHasNewerVersion,
      clearDraft: state.clearDraft,
    })),
  );
  const { stageValidatedPatch } = useStagedScheduleActions();

  const [selectedDateStr, setSelectedDateStr] = useQueryState("date");
  const [isTwoWeekView, setIsTwoWeekView] = useQueryState(
    "isTwoWeek",
    parseAsBoolean.withDefault(true),
  );
  const [anchorDateStr, setAnchorDateStr] = useQueryState(
    "anchor",
    parseAsString.withDefault(TODAY_STRING),
  );
  const [selectedShiftId, setSelectedShiftId] = useQueryState("shift");
  const [selectedNurseId, setSelectedNurseId] = useQueryState("nurseId");

  const { calendarDays, currentViewAnchorDate } = useScheduleCalendar({
    effectiveScheduleMap,
    isLoading,
    anchorDateStr,
    isTwoWeekView,
  });

  const runIsActive = isRunActive(activeRun?.status);

  const triggerOptimization = useCallback(
    async (allowOverwrite = false) => {
      if (!selectedFacility || !scheduleId) {
        toast.error("Optimization unavailable", {
          description: "No facility schedule is loaded yet.",
        });
        return;
      }

      if (runIsActive) {
        toast.info("Optimization already running", {
          description: "Wait for the current run to finish before starting another.",
        });
        return;
      }

      const startDate = new Date(currentViewAnchorDate);
      startDate.setDate(startDate.getDate() - 2);
      const endDate = new Date(currentViewAnchorDate);
      endDate.setDate(endDate.getDate() + 5);

      try {
        const status = await getScheduleStatus({
          orgId: selectedFacility.orgId,
          facilityId: selectedFacility.facilityId,
          scheduleId,
          currentScheduleVersion: scheduleVersion,
        });

        setHasNewerVersion(status.hasNewerVersion, status.latestScheduleVersion);
        if (status.hasNewerVersion && !allowOverwrite) {
          toast.error("Newer schedule version available", {
            description: "Refresh or explicitly continue with overwrite before optimizing.",
          });
          return;
        }

        const response = await startOptimizationRun({
          orgId: selectedFacility.orgId,
          facilityId: selectedFacility.facilityId,
          scheduleId,
          baseScheduleVersion: scheduleVersion,
          startDate: formatDateYYYYMMDD(startDate),
          endDate: formatDateYYYYMMDD(endDate),
          settings: optimizationSettingsToProto(schedulerSettings),
          persistResult: true,
          clientRequestId: createClientUuid(),
          stagedPatches: draftState.patches.map(toProtoPatch),
          allowOverwrite,
        });

        if (response.versionConflict) {
          setHasNewerVersion(true, response.latestScheduleVersion);
        }

        const conflicts: UIPatchConflict[] = response.conflicts.map(protoPatchConflictToUI);
        if (hasBlockingConflicts(response.conflicts)) {
          setDraftConflicts(conflicts);
          toast.error("Optimization blocked by draft conflicts", {
            description: "Resolve staged patch conflicts before retrying.",
          });
          return;
        }

        if (!response.accepted || !response.run) {
          toast.error("Optimization failed to start", {
            description: response.errorDetails || "The backend did not accept the run.",
          });
          return;
        }

        const uiRun = protoOptimizationRunToUI(response.run);
        if (!uiRun) {
          toast.error("Optimization failed to start", {
            description: "The run response was incomplete.",
          });
          return;
        }

        setActiveRun(uiRun);
        toast.success("Optimization started", {
          description: "Run progress will continue across refreshes.",
        });
      } catch (error) {
        toast.error("Optimization failed", {
          description: error instanceof Error ? error.message : "Unexpected optimizer error",
        });
      }
    },
    [
      currentViewAnchorDate,
      draftState.patches,
      runIsActive,
      scheduleId,
      scheduleVersion,
      schedulerSettings,
      selectedFacility,
      setActiveRun,
      setDraftConflicts,
      setHasNewerVersion,
    ],
  );

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
    return isTwoWeekView ? TODAY : currentViewAnchorDate;
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
      setAnchorDateStr(formatDateYYYYMMDD(TODAY));
    } else {
      setAnchorDateStr(formatDateYYYYMMDD(getStartOfMonth(TODAY)));
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
    isRunActive: runIsActive,
    removeNurseFromShift,
    stageShiftRemoval,
    addNurseToShift,
    toggleCalendarView,
    triggerOptimization,
    clearDraft,
    updateSchedulerSettings,
    SHIFT_NAMES,
  };
}

export { defaultSchedulerSettings };
