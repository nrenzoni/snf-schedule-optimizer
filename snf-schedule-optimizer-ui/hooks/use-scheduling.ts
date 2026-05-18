import {
  UICalendarDay,
  UINurse,
  UIShift,
  UISchedulerSettings,
} from "@/types/scheduling";
import {
  SHIFT_NAMES,
} from "@/lib/scheduling-logic";
import {
  useSchedulingStore,
  defaultSchedulerSettings,
} from "@/store/schedulingStore";
import { useShallow } from "zustand/react/shallow";
import { useStagedScheduleActions } from "@/hooks/use-staged-schedule-actions";
import { useScheduleNavigation } from "@/hooks/use-schedule-navigation";
import { useOptimizationTrigger } from "@/hooks/use-optimization-trigger";

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
    setPendingRunCapture,
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
      setPendingRunCapture: state.setPendingRunCapture,
    })),
  );
  const { stageValidatedPatch } = useStagedScheduleActions();

  const nav = useScheduleNavigation({
    effectiveScheduleMap,
    isLoading,
    selectedFacility,
    scheduleId,
    schedulerSettings,
    setSchedulerSettings,
    draftState,
    clearDraft,
    setHasPendingValidation,
    stageValidatedPatch,
  });

  const opt = useOptimizationTrigger({
    selectedFacility,
    scheduleId,
    scheduleVersion,
    schedulerSettings,
    draftState,
    activeRun,
    currentViewAnchorDate: nav.currentViewAnchorDate,
    effectiveScheduleMap,
    setActiveRun,
    setDraftConflicts,
    setHasNewerVersion,
    setPendingRunCapture,
  });

  return {
    selectedDay: nav.selectedDay,
    selectedShift: nav.selectedShift,
    selectedNurse: nav.selectedNurse,
    isModalVisible: nav.isModalVisible,
    openShiftDetails: nav.openShiftDetails,
    closeModal: nav.closeModal,
    selectShift: nav.selectShift,
    openNurseDetails: nav.openNurseDetails,
    closeNurseDetails: nav.closeNurseDetails,
    changeMonth: nav.changeMonth,
    currentDate: nav.currentDate,
    calendarDays: nav.calendarDays,
    isTwoWeekView: nav.isTwoWeekView,
    isRunActive: opt.isRunActive,
    removeNurseFromShift: nav.removeNurseFromShift,
    stageShiftRemoval: nav.stageShiftRemoval,
    addNurseToShift: nav.addNurseToShift,
    toggleCalendarView: nav.toggleCalendarView,
    triggerOptimization: opt.triggerOptimization,
    clearDraft: nav.clearDraft,
    updateSchedulerSettings: nav.updateSchedulerSettings,
    SHIFT_NAMES: nav.SHIFT_NAMES,
  };
}

export { defaultSchedulerSettings };
