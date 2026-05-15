import { useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useShallow } from "zustand/react/shallow";
import { pollOptimizationRun, streamOptimizationRun } from "@/api/scheduling-client";
import { useSchedulingStore } from "@/store/schedulingStore";
import { protoOptimizationRunToUI } from "@/lib/proto-mappers";
import { isRunActive } from "@/lib/scheduling-helpers";

export function useOptimizationRunSync() {
  const queryClient = useQueryClient();
  const { activeRun, setRunProgress } = useSchedulingStore(
    useShallow((state) => ({
      activeRun: state.activeRun,
      setRunProgress: state.setRunProgress,
    })),
  );
  const runStreamAbortRef = useRef<AbortController | null>(null);
  const activeRunRef = useRef(activeRun);
  const latestSequenceByRunRef = useRef(new Map<string, number>());

  useEffect(() => {
    activeRunRef.current = activeRun;
  }, [activeRun]);

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

            const sequence = Number(event.sequence);
            const latestSequence = latestSequenceByRunRef.current.get(runId) ?? -1;
            if (Number.isFinite(sequence) && sequence <= latestSequence) {
              return;
            }

            const currentRun = activeRunRef.current;
            if (currentRun?.runId === uiRun.runId) {
              const regressedToQueued = currentRun.status === "running" && uiRun.status === "queued";
              const regressedProgress = uiRun.progressPercent < currentRun.progressPercent;
              if (regressedToQueued || regressedProgress) {
                return;
              }
            }

            if (Number.isFinite(sequence)) {
              latestSequenceByRunRef.current.set(runId, sequence);
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

  const activeRunId = activeRun?.runId;

  useEffect(() => {
    if (!activeRunId || !isRunActive(activeRunRef.current?.status)) {
      runStreamAbortRef.current?.abort();
      return;
    }
    void syncRunProgress(activeRunId);
    return () => {
      runStreamAbortRef.current?.abort();
    };
  }, [activeRunId, syncRunProgress]);
}
