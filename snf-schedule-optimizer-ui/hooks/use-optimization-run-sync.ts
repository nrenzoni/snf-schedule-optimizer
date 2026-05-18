import { useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useShallow } from "zustand/react/shallow";
import { pollOptimizationRun, streamOptimizationRun } from "@/api/scheduling-client";
import { useSchedulingStore } from "@/store/schedulingStore";
import { protoOptimizationRunToUI } from "@/lib/proto-mappers";
import { isRunActive } from "@/lib/scheduling-helpers";
import type { StageTiming, UIOptimizationRunStage } from "@/types/scheduling";

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
  const stageEntryTimesRef = useRef<Map<string, number>>(new Map());
  const stageTimingsRef = useRef<StageTiming[]>([]);
  const lastStageRef = useRef<UIOptimizationRunStage | null>(null);

  useEffect(() => {
    activeRunRef.current = activeRun;
  }, [activeRun]);

  const refetchSchedule = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["schedule"] });
  }, [queryClient]);

  const recordStageTiming = useCallback((newStage: UIOptimizationRunStage) => {
    const now = Date.now();
    const prevStage = lastStageRef.current;

    if (prevStage && prevStage !== newStage && stageEntryTimesRef.current.has(prevStage)) {
      const entryMs = stageEntryTimesRef.current.get(prevStage)!;
      const durationMs = now - entryMs;
      stageTimingsRef.current = [
        ...stageTimingsRef.current,
        { stage: prevStage, durationMs },
      ];
    }

    if (!stageEntryTimesRef.current.has(newStage)) {
      stageEntryTimesRef.current.set(newStage, now);
    }
    lastStageRef.current = newStage;
  }, []);

  const finalizeStageTimings = useCallback((finalStage: UIOptimizationRunStage) => {
    const now = Date.now();
    const prevStage = lastStageRef.current;

    if (prevStage && prevStage !== finalStage && stageEntryTimesRef.current.has(prevStage)) {
      const entryMs = stageEntryTimesRef.current.get(prevStage)!;
      stageTimingsRef.current = [
        ...stageTimingsRef.current,
        { stage: prevStage, durationMs: now - entryMs },
      ];
    }

    if (stageEntryTimesRef.current.has(finalStage)) {
      const entryMs = stageEntryTimesRef.current.get(finalStage)!;
      stageTimingsRef.current = [
        ...stageTimingsRef.current,
        { stage: finalStage, durationMs: now - entryMs },
      ];
    }

    lastStageRef.current = finalStage;
  }, []);

  const pollAndApplyFinalRun = useCallback(async (runId: string) => {
    const latest = await pollOptimizationRun(runId).catch(() => null);
    const uiRun = protoOptimizationRunToUI(latest?.run);
    if (uiRun) {
      recordStageTiming(uiRun.stage);
      if (!isRunActive(uiRun.status)) {
        finalizeStageTimings(uiRun.stage);
      }
      setRunProgress({ ...uiRun, stageTimings: uiRun.stageTimings.length > 0 ? uiRun.stageTimings : [...stageTimingsRef.current] });
      if (!isRunActive(uiRun.status)) {
        await refetchSchedule();
      }
    }
  }, [refetchSchedule, setRunProgress, recordStageTiming, finalizeStageTimings]);

  const syncRunProgress = useCallback(
    async (runId: string) => {
      runStreamAbortRef.current?.abort();
      const abortController = new AbortController();
      runStreamAbortRef.current = abortController;

      stageEntryTimesRef.current = new Map();
      stageTimingsRef.current = [];
      lastStageRef.current = null;

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

            recordStageTiming(uiRun.stage);

            if (!isRunActive(uiRun.status)) {
              finalizeStageTimings(uiRun.stage);
            }

            setRunProgress({
              ...uiRun,
              stageTimings: [...stageTimingsRef.current],
            });

            if (!isRunActive(uiRun.status)) {
              void refetchSchedule().catch(console.error);
              abortController.abort();
            }
          },
          abortController.signal,
        );

        await pollAndApplyFinalRun(runId);
      } catch {
        if (abortController.signal.aborted) {
          return;
        }

        await pollAndApplyFinalRun(runId);
      }
    },
    [refetchSchedule, setRunProgress, pollAndApplyFinalRun, recordStageTiming, finalizeStageTimings],
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
