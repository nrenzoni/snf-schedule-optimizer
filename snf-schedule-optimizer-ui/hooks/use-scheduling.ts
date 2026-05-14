import { useCallback, useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";
import {
  UICalendarDay,
  UINurse,
  UIPatchConflict,
  UISchedulerSettings,
  UIShift,
  UIStagedPatch,
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
import {
  getScheduleStatus,
  hasBlockingConflicts,
  pollOptimizationRun,
  startOptimizationRun,
  streamOptimizationRun,
} from "@/api/scheduling-client";
import {
  defaultSchedulerSettings,
  useSchedulingStore,
} from "@/store/schedulingStore";
import { useShallow } from "zustand/react/shallow";
import { parseAsBoolean, parseAsString, useQueryState } from "nuqs";
import { OptimizationSettings, StagedSchedulePatchSchema } from "@/gen/scheduling/v1/scheduling_pb";
import { create } from "@bufbuild/protobuf";
import {
  protoOptimizationRunToUI,
  protoPatchConflictToUI,
} from "@/hooks/use-schedule-query";
import { createClientUuid } from "@/lib/utils";

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

const toProtoPatch = (patch: UIStagedPatch) =>
  create(StagedSchedulePatchSchema, {
    patchId: patch.patchId,
    employeeId: patch.employeeId,
    employeeName: patch.employeeName ?? "",
    fromShiftId: patch.fromShiftId ?? "",
    toShiftId: patch.toShiftId ?? "",
    pinned: patch.pinned,
    warnings: patch.warnings,
    totalCost: patch.totalCost,
    causesOvertime: patch.causesOvertime,
    createdAt: patch.createdAt ?? "",
  });

const isRunActive = (status: string | null | undefined) => status === "queued" || status === "running";

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
    setRunProgress,
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
      setRunProgress: state.setRunProgress,
      setHasNewerVersion: state.setHasNewerVersion,
      clearDraft: state.clearDraft,
    })),
  );

  const runStreamAbortRef = useRef<AbortController | null>(null);

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
  const runIsActive = isRunActive(activeRun?.status);

  const syncRunProgress = useCallback(
    async (runId: string) => {
      runStreamAbortRef.current?.abort();
      const abortController = new AbortController();
      runStreamAbortRef.current = abortController;

      try {
        await streamOptimizationRun(runId, (event) => {
          if (abortController.signal.aborted) {
            return;
          }
          const uiRun = protoOptimizationRunToUI(event.run);
          if (!uiRun) {
            return;
          }
          setRunProgress(uiRun);
          if (!isRunActive(uiRun.status)) {
            abortController.abort();
          }
        });
      } catch {
        if (abortController.signal.aborted) {
          return;
        }

        const latest = await pollOptimizationRun(runId).catch(() => null);
        const uiRun = protoOptimizationRunToUI(latest?.run);
        if (uiRun) {
          setRunProgress(uiRun);
        }
      }
    },
    [setRunProgress],
  );

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
      const endDate = new Date(startDate);
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
          startDate: formatDateYYYMMDD(startDate),
          endDate: formatDateYYYMMDD(endDate),
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
        void syncRunProgress(uiRun.runId);
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
      syncRunProgress,
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
      const schedule = effectiveScheduleMap.get(dayDateString) || null;
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
  }, [currentViewAnchorDate, effectiveScheduleMap, isTwoWeekView, isLoading]);

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

  const removeNurseFromShift = useCallback(async (): Promise<void> => {
    toast.info("Shift edits now use drag and drop staging", {
      description: "Use the schedule board to stage and validate pinned changes.",
    });
  }, []);

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
    const runId = activeRun?.runId;
    if (!runId || !runIsActive) {
      runStreamAbortRef.current?.abort();
      return;
    }
    void syncRunProgress(runId);
    return () => {
      runStreamAbortRef.current?.abort();
    };
  }, [activeRun?.runId, runIsActive, syncRunProgress]);

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
    addNurseToShift,
    toggleCalendarView,
    triggerOptimization,
    clearDraft,
    updateSchedulerSettings,
    SHIFT_NAMES,
  };
}

export { defaultSchedulerSettings };
