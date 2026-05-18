"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Network, X } from "lucide-react";
import ModalContainer from "@/components/modal-container";
import OptimizationTreeNode from "@/components/optimization-tree-node";
import { useSchedulingStore } from "@/store/schedulingStore";
import { buildTreeData, TreeNode } from "@/lib/optimization-tree-data";
import { scheduleMapToRecord } from "@/store/schedule-data-slice";
import { iconButtonVariants } from "@/components/ui/styles";
import { cn } from "@/lib/utils";
import type { RunHistoryEntry, ScheduleMap, UIDaySchedule } from "@/types/scheduling";

interface OptimizationTreeModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentScheduleMap: ScheduleMap;
}

export function OptimizationTreeModal({
  isOpen,
  onClose,
  currentScheduleMap,
}: OptimizationTreeModalProps) {
  const completedRuns = useSchedulingStore((s) => s.completedRuns);

  const [selectedRunIndex, setSelectedRunIndex] = useState(() =>
    completedRuns.length > 0 ? completedRuns.length - 1 : 0,
  );
  const [newRunGlow, setNewRunGlow] = useState(false);
  const prevRunCountRef = useRef(completedRuns.length);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (completedRuns.length > prevRunCountRef.current) {
      const prev = prevRunCountRef.current;
      prevRunCountRef.current = completedRuns.length;

      const wasOnLatest = selectedRunIndex === prev - 1 && prev > 0;
      if (wasOnLatest && completedRuns.length > 0) {
        setSelectedRunIndex(completedRuns.length - 1);
      } else if (prev > 0) {
        setNewRunGlow(true);
        const timer = setTimeout(() => setNewRunGlow(false), 1500);
        return () => clearTimeout(timer);
      }
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [completedRuns.length, selectedRunIndex]);

  useEffect(() => {
    if (isOpen && completedRuns.length > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedRunIndex((prev) => Math.min(prev, completedRuns.length - 1));
    }
  }, [isOpen, completedRuns.length]);

  const selectedEntry: RunHistoryEntry | null =
    completedRuns.length > 0 && selectedRunIndex >= 0 && selectedRunIndex < completedRuns.length
      ? completedRuns[selectedRunIndex]
      : null;

  const postSchedule: Record<string, UIDaySchedule> = useMemo(
    () => scheduleMapToRecord(currentScheduleMap),
    [currentScheduleMap],
  );

  const treeData: TreeNode[] = useMemo(() => {
    if (!selectedEntry) return [];
    return buildTreeData(selectedEntry, postSchedule);
  }, [selectedEntry, postSchedule]);

  const handlePrev = useCallback(() => {
    setSelectedRunIndex((prev) => Math.max(0, prev - 1));
    setNewRunGlow(false);
  }, []);

  const handleNext = useCallback(() => {
    setSelectedRunIndex((prev) => Math.min(completedRuns.length - 1, prev + 1));
    setNewRunGlow(false);
  }, [completedRuns.length]);

  const isLatest = selectedRunIndex === completedRuns.length - 1;
  const isOldest = selectedRunIndex === 0;

  if (!isOpen) return null;

  return (
    <ModalContainer isOpen={isOpen} onClose={onClose} contentClassName="max-w-3xl">
      <div className="w-full overflow-hidden">
        <div className="app-modal-header">
          <div className="flex items-center gap-2">
            <Network size={24} />
            <h3 className="text-xl font-black">Optimization Results</h3>
          </div>
          <div className="flex items-center gap-2">
            {completedRuns.length > 1 && (
              <div className="flex items-center gap-1 mr-3">
                <button
                  data-testid="tree-prev-run"
                  onClick={handlePrev}
                  disabled={isOldest}
                  className={iconButtonVariants({ tone: "soft", disabled: isOldest })}
                  aria-label="Previous optimization run"
                >
                  <ArrowLeft size={16} />
                </button>
                <span className="min-w-[4rem] text-center text-xs text-muted-foreground font-mono tabular-nums">
                  {selectedRunIndex + 1} of {completedRuns.length}
                </span>
                <button
                  data-testid="tree-next-run"
                  onClick={handleNext}
                  disabled={isLatest && !newRunGlow}
                  className={cn(
                    iconButtonVariants({ tone: "soft", disabled: isLatest && !newRunGlow }),
                    newRunGlow && "animate-pulse ring-2 ring-primary ring-offset-1 rounded-lg",
                  )}
                  aria-label="Next optimization run"
                >
                  <ArrowRight size={16} />
                </button>
              </div>
            )}
            <button
              data-testid="tree-modal-close"
              onClick={onClose}
              className={iconButtonVariants({ tone: "soft" })}
              aria-label="Close results"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {!selectedEntry ? (
          <div className="flex flex-col items-center justify-center gap-4 px-6 py-16 text-muted-foreground">
            <Network size={48} className="opacity-30" />
            <p className="text-sm">No completed optimization runs yet.</p>
            <p className="text-xs">Run an optimization to see results here.</p>
          </div>
        ) : (
          <div className="max-h-[65vh] overflow-y-auto px-2 py-3" role="tree" data-testid="optimization-tree">
            {treeData.map((node) => (
              <OptimizationTreeNode key={node.id} node={node} depth={0} />
            ))}
          </div>
        )}
      </div>
    </ModalContainer>
  );
}
