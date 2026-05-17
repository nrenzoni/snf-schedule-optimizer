import { useCallback, useRef } from "react";
import { toast } from "sonner";
import {
  UIDraftState,
  UIPatchConflict,
  UISchedulerSettings,
} from "@/types/scheduling";
import { formatDateYYYYMMDD } from "@/lib/scheduling-logic";
import {
  getScheduleStatus,
  hasBlockingConflicts,
  startOptimizationRun,
} from "@/api/scheduling-client";
import { OptimizationSettings } from "@/gen/scheduling/v1/scheduling_pb";
import {
  protoOptimizationRunToUI,
  protoPatchConflictToUI,
} from "@/lib/proto-mappers";
import { isRunActive, toProtoPatch } from "@/lib/scheduling-helpers";
import { createClientUuid } from "@/lib/utils";
import type { OrgFacility } from "@/gen/scheduling/v1/scheduling_pb";
import type { UIOptimizationRun } from "@/types/scheduling";

export interface UseOptimizationTriggerReturn {
  triggerOptimization: (allowOverwrite?: boolean) => Promise<void>;
  isRunActive: boolean;
}

interface UseOptimizationTriggerProps {
  selectedFacility: OrgFacility | null;
  scheduleId: string | null;
  scheduleVersion: number;
  schedulerSettings: UISchedulerSettings;
  draftState: UIDraftState;
  activeRun: UIOptimizationRun | null;
  currentViewAnchorDate: Date;
  setActiveRun: (run: UIOptimizationRun | null) => void;
  setDraftConflicts: (conflicts: UIPatchConflict[]) => void;
  setHasNewerVersion: (hasNewer: boolean, version: number) => void;
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

export function useOptimizationTrigger({
  selectedFacility,
  scheduleId,
  scheduleVersion,
  schedulerSettings,
  draftState,
  activeRun,
  currentViewAnchorDate,
  setActiveRun,
  setDraftConflicts,
  setHasNewerVersion,
}: UseOptimizationTriggerProps): UseOptimizationTriggerReturn {
  const runIsActive = isRunActive(activeRun?.status);
  const isTriggeringRef = useRef(false);

  const triggerOptimization = useCallback(
    async (allowOverwrite = false) => {
      if (isTriggeringRef.current) return;
      isTriggeringRef.current = true;
      try {
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
      } finally {
        isTriggeringRef.current = false;
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

  return {
    triggerOptimization,
    isRunActive: runIsActive,
  };
}
