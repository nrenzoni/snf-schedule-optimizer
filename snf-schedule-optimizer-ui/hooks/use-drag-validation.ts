import { useCallback, useState } from "react";
import { DragEndEvent } from "@dnd-kit/core";
import { startOfWeek } from "date-fns";
import { toast } from "sonner";
import {
  MoveValidationPreview,
  Shift,
  TimelineSlotData,
} from "@/types/scheduler";
import { UIDraftState, UIPatchConflict } from "@/types/scheduling";
import { validateShiftMove } from "@/api/scheduling-client";
import { protoPatchConflictToUI, protoStagedPatchToUI } from "@/lib/proto-mappers";
import { toProtoPatch } from "@/lib/scheduling-helpers";
import { createClientUuid } from "@/lib/utils";
import type { OrgFacility } from "@/gen/scheduling/v1/scheduling_pb";

interface UseDragValidationProps {
  selectedFacility: OrgFacility | null;
  scheduleId: string | null;
  scheduleVersion: number;
  draftState: UIDraftState;
  dragDisabled: boolean;
  appendDraftPatch: (patch: import("@/types/scheduling").UIStagedPatch) => void;
  setDraftConflicts: (conflicts: UIPatchConflict[]) => void;
  setHasPendingValidation: (value: boolean) => void;
}

interface UseDragValidationReturn {
  handleDragEnd: (event: DragEndEvent) => Promise<void>;
  pendingSlotId: string | null;
  validationPreview: MoveValidationPreview | null;
  setPendingSlotId: (id: string | null) => void;
  setValidationPreview: (preview: MoveValidationPreview | null) => void;
}

export function useDragValidation({
  selectedFacility,
  scheduleId,
  scheduleVersion,
  draftState,
  dragDisabled,
  appendDraftPatch,
  setDraftConflicts,
  setHasPendingValidation,
}: UseDragValidationProps): UseDragValidationReturn {
  const [pendingSlotId, setPendingSlotId] = useState<string | null>(null);
  const [validationPreview, setValidationPreview] =
    useState<MoveValidationPreview | null>(null);

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      const { active, over } = event;
      setPendingSlotId(null);

      if (!over) {
        setValidationPreview(null);
        return;
      }

      const activeData = active.data.current?.shift as Shift | undefined;
      const overData = over.data.current as TimelineSlotData | undefined;

      if (
        !activeData ||
        !overData ||
        !selectedFacility ||
        !scheduleId ||
        !overData.shiftId ||
        dragDisabled
      ) {
        setValidationPreview(null);
        return;
      }

      if (activeData.shiftId === overData.shiftId) {
        setValidationPreview(null);
        return;
      }

      try {
        setHasPendingValidation(true);
        const slotId = String(over.id);
        setPendingSlotId(slotId);

        const payPeriodStart = startOfWeek(new Date(activeData.dateStr), { weekStartsOn: 0 });
        const response = await validateShiftMove({
          orgId: selectedFacility.orgId,
          facilityId: selectedFacility.facilityId,
          scheduleId,
          employeeId: activeData.staffId,
          fromShiftId: activeData.shiftId,
          toShiftId: overData.shiftId,
          payPeriodStartTs: BigInt(Math.floor(payPeriodStart.getTime() / 1000)),
          scheduleVersion,
          stagedPatches: draftState.patches.map(toProtoPatch),
          patchId: createClientUuid(),
        });

        const preview: MoveValidationPreview = {
          validationLevel: response.isStale
            ? "stale"
            : response.patch
              ? protoStagedPatchToUI(response.patch).validationLevel
              : response.isValid
                ? "ok"
                : "critical",
          warnings: response.warnings,
          causesOvertime: response.patch?.causesOvertime ?? false,
          totalCost: response.totalCost,
          isValid: response.isValid,
          errorDetails: response.errorDetails || undefined,
        };
        setValidationPreview(preview);

        if (!response.isSuccess) {
          toast.error("Move validation failed", {
            description: response.errorDetails || "The backend could not validate this move.",
          });
          return;
        }

        if (response.isStale) {
          toast.error("Schedule changed on the server", {
            description: "Refresh before applying more staged changes.",
          });
          return;
        }

        if (response.conflicts.length > 0) {
          setDraftConflicts(response.conflicts.map(protoPatchConflictToUI));
        }

        if (!response.isValid || !response.patch) {
          toast.error("Move blocked", {
            description: response.errorDetails || response.warnings.join(" ") || "This move is not allowed.",
          });
          return;
        }

        appendDraftPatch(protoStagedPatchToUI(response.patch));
        toast.success("Pinned change staged", {
          description:
            response.warnings.join(" ") ||
            (response.patch.causesOvertime
              ? "Move staged with overtime warning."
              : "Validated move staged locally until optimization."),
        });
      } catch (error) {
        toast.error("Move validation failed", {
          description: error instanceof Error ? error.message : "Unexpected scheduling error",
        });
      } finally {
        setPendingSlotId(null);
        setHasPendingValidation(false);
      }
    },
    [
      appendDraftPatch,
      draftState.patches,
      dragDisabled,
      scheduleId,
      scheduleVersion,
      selectedFacility,
      setDraftConflicts,
      setHasPendingValidation,
    ],
  );

  return {
    handleDragEnd,
    pendingSlotId,
    validationPreview,
    setPendingSlotId,
    setValidationPreview,
  };
}
