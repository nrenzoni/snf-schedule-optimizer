import { useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useShallow } from "zustand/react/shallow";
import { pollOptimizationRun, streamOptimizationRun } from "@/api/scheduling-client";
import { protoOptimizationRunToUI } from "@/hooks/use-schedule-query";
import { useSchedulingStore } from "@/store/schedulingStore";

const isRunActive = (status: string | null | undefined) => status === "queued" || status === "running";

export function useOptimizationRunSync() {
  const queryClient = useQueryClient();
  const { activeRun, setRunProgress } = useSchedulingStore(
    useShallow((state) => ({
      activeRun: state.activeRun,
      setRunProgress: state.setRunProgress,
    })),
  );
  const runStreamAbortRef = useRef<AbortController | null>(null);

  const refetchSchedule = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["schedule"] });
  }, [queryClient]);

  const syncRunProgress = useCallback(
    async (runId: string) => {
      runStreamAbortRef.current?.abort();
      const abortController = new AbortController();
      runStreamAbortRef.current = abortController;

      try {
        await streamOptimizationRun(
          runId,
          (event) => {
            if (abortController.signal.aborted) {
              return;
            }

            const uiRun = protoOptimizationRunToUI(event.run);
            if (!uiRun) {
              return;
            }

            setRunProgress(uiRun);
            if (!isRunActive(uiRun.status)) {
              void refetchSchedule();
              abortController.abort();
            }
          },
          abortController.signal,
        );

        const latest = await pollOptimizationRun(runId).catch(() => null);
        const uiRun = protoOptimizationRunToUI(latest?.run);
        if (uiRun) {
          setRunProgress(uiRun);
          if (!isRunActive(uiRun.status)) {
            await refetchSchedule();
          }
        }
      } catch {
        if (abortController.signal.aborted) {
          return;
        }

        const latest = await pollOptimizationRun(runId).catch(() => null);
        const uiRun = protoOptimizationRunToUI(latest?.run);
        if (uiRun) {
          setRunProgress(uiRun);
          if (!isRunActive(uiRun.status)) {
            await refetchSchedule();
          }
        }
      }
    },
    [refetchSchedule, setRunProgress],
  );

  useEffect(() => {
    const runId = activeRun?.runId;
    if (!runId || !isRunActive(activeRun?.status)) {
      runStreamAbortRef.current?.abort();
      return;
    }
    void syncRunProgress(runId);
    return () => {
      runStreamAbortRef.current?.abort();
    };
  }, [activeRun?.runId, activeRun?.status, syncRunProgress]);
}
