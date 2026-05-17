import { useCallback, useEffect, useRef } from "react";
import { toast } from "sonner";
import { useShallow } from "zustand/react/shallow";
import { useSchedulingStore } from "@/store/schedulingStore";
import { validateShiftMove } from "@/api/scheduling-client";
import { createClientUuid } from "@/lib/utils";
import { protoPatchConflictToUI, protoStagedPatchToUI } from "@/lib/proto-mappers";
import { toProtoPatch } from "@/lib/scheduling-helpers";

export function useStagedScheduleActions() {
  const {
    selectedFacility,
    scheduleId,
    scheduleVersion,
    draftState,
    appendDraftPatch,
    setDraftConflicts,
    setHasPendingValidation,
  } = useSchedulingStore(
    useShallow((state) => ({
      selectedFacility: state.selectedFacility,
      scheduleId: state.scheduleId,
      scheduleVersion: state.scheduleVersion,
      draftState: state.draftState,
      appendDraftPatch: state.appendDraftPatch,
      setDraftConflicts: state.setDraftConflicts,
      setHasPendingValidation: state.setHasPendingValidation,
    })),
  );

  const patchesRef = useRef(draftState.patches);
  useEffect(() => { patchesRef.current = draftState.patches; }, [draftState.patches]);

  const stageValidatedPatch = useCallback(
    async (input: {
      employeeId: string;
      employeeName?: string | null;
      fromShiftId: string | null;
      toShiftId: string | null;
      payPeriodStart: Date;
      successTitle: string;
      successDescription?: string;
    }) => {
      if (!selectedFacility || !scheduleId) {
        toast.error("Schedule edit unavailable", {
          description: "No facility schedule is loaded yet.",
        });
        return false;
      }

      try {
        setHasPendingValidation(true);

        const response = await validateShiftMove({
          orgId: selectedFacility.orgId,
          facilityId: selectedFacility.facilityId,
          scheduleId,
          employeeId: input.employeeId,
          fromShiftId: input.fromShiftId ?? "",
          toShiftId: input.toShiftId ?? "",
          payPeriodStartTs: BigInt(Math.floor(input.payPeriodStart.getTime() / 1000)),
          scheduleVersion,
          stagedPatches: patchesRef.current.map(toProtoPatch),
          patchId: createClientUuid(),
        });

        if (!response.isSuccess) {
          toast.error("Schedule edit failed", {
            description: response.errorDetails || "The backend could not validate this change.",
          });
          return false;
        }

        if (response.isStale) {
          toast.error("Schedule changed on the server", {
            description: "Refresh before applying more staged changes.",
          });
          return false;
        }

        if (response.conflicts.length > 0) {
          setDraftConflicts(response.conflicts.map(protoPatchConflictToUI));
        }

        if (!response.isValid || !response.patch) {
          toast.error("Schedule edit blocked", {
            description: response.errorDetails || response.warnings.join(" ") || "This change is not allowed.",
          });
          return false;
        }

        appendDraftPatch(protoStagedPatchToUI(response.patch));
        toast.success(input.successTitle, {
          description:
            response.warnings.join(" ") ||
            input.successDescription ||
            "Validated change staged locally until optimization.",
        });
        return true;
      } catch (error) {
        toast.error("Schedule edit failed", {
          description: error instanceof Error ? error.message : "Unexpected scheduling error",
        });
        return false;
      } finally {
        setHasPendingValidation(false);
      }
    },
    [
      appendDraftPatch,
      scheduleId,
      scheduleVersion,
      selectedFacility,
      setDraftConflicts,
      setHasPendingValidation,
    ],
  );

  return { stageValidatedPatch };
}
