import { useState, useEffect, useRef } from "react";
import { isRunActive } from "@/lib/scheduling-helpers";
import type { UIOptimizationRun, UIOptimizationRunStage } from "@/types/scheduling";

const STAGE_LABELS: Record<UIOptimizationRunStage, string> = {
  unspecified: "Preparing",
  queued: "Queued",
  snapshotting: "Snapshotting",
  indexing: "Indexing",
  building_model: "Building Model",
  solving: "Solving",
  analyzing: "Analyzing",
  publishing: "Publishing",
  completed: "Completed",
  failed: "Failed",
};

export interface AnimatedProgress {
  percent: number;
  stage: string;
  stageElapsed: number;
}

export function useAnimatedProgress(
  activeRun: UIOptimizationRun | null,
): AnimatedProgress {
  const [displayPercent, setDisplayPercent] = useState(0);
  const lastChangeTimeMsRef = useRef(0);
  const lastTargetRef = useRef(0);
  const prevRunIdRef = useRef<string | null>(null);
  const activeRunRef = useRef(activeRun);
  const stageStartMsRef = useRef(0);
  const stageRef = useRef<UIOptimizationRunStage>("unspecified");
  const [stageElapsed, setStageElapsed] = useState(0);

  useEffect(() => {
    activeRunRef.current = activeRun;
  });

  useEffect(() => {
    const interval = setInterval(() => {
      const run = activeRunRef.current;
      const currentRunId = run?.runId ?? null;
      const active = run !== null && isRunActive(run.status);

      // Track stage elapsed time
      if (active && run) {
        if (run.stage !== stageRef.current) {
          stageRef.current = run.stage;
          stageStartMsRef.current = performance.now();
          setStageElapsed(0);
        } else {
          setStageElapsed(
            Math.floor((performance.now() - stageStartMsRef.current) / 1000),
          );
        }
      } else {
        setStageElapsed(0);
      }

      if (currentRunId !== prevRunIdRef.current) {
        prevRunIdRef.current = currentRunId;
        if (run && isRunActive(run.status)) {
          lastChangeTimeMsRef.current = performance.now();
          lastTargetRef.current = run.progressPercent;
          setDisplayPercent(run.progressPercent);
        } else {
          setDisplayPercent(run ? run.progressPercent : 0);
        }
        return;
      }

      if (!active) {
        setDisplayPercent(run ? run.progressPercent : 0);
        return;
      }

      setDisplayPercent((prev) => {
        const target = run!.progressPercent;

        if (target !== lastTargetRef.current) {
          lastChangeTimeMsRef.current = performance.now();
          lastTargetRef.current = target;
        }

        if (target > prev + 0.5) {
          const gap = target - prev;
          return Math.min(target, prev + gap * 0.15);
        }

        const stalledMs = performance.now() - lastChangeTimeMsRef.current;
        if (stalledMs >= 5000 && prev < 98) {
          const next = prev + 0.3;
          const cap = target >= 100 ? 100 : Math.min(target + 5, 99);
          return Math.min(next, cap);
        }

        if (prev > 99 && target < 100) {
          return 99;
        }

        return prev;
      });
    }, 100);

    return () => clearInterval(interval);
  }, []);

  const stage =
    activeRun && isRunActive(activeRun.status)
      ? STAGE_LABELS[activeRun.stage] ?? activeRun.stage
      : "";

  return { percent: displayPercent, stage, stageElapsed };
}
