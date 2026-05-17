import React from "react";
import { Zap, ListChecks, Settings, LayoutList, GanttChartSquare } from "lucide-react";
import { segmentedButtonVariants } from "@/components/ui/styles";
import { viewOptions } from "@/components/dashboard-content";
import { UIPatchConflict } from "@/types/scheduling";

interface DashboardControlsProps {
  hasNewerVersion: boolean;
  latestKnownScheduleVersion: number;
  draftPatchCount: number;
  draftConflicts: UIPatchConflict[];
  clearDraft: () => void;
  triggerOptimization: (allowOverwrite?: boolean) => Promise<void>;
  isRunActive: boolean;
  activeRun: {
    progressPercent: number;
    stage?: string;
    statusMessage?: string;
  } | null;
  optimizeButtonFillWidth: string;
  uiStore: {
    openSummaryModal: () => void;
    openConfigModal: () => void;
  };
  viewMode: (typeof viewOptions)[number];
  setViewMode: (value: (typeof viewOptions)[number]) => Promise<URLSearchParams>;
}

export default function DashboardControls({
  hasNewerVersion,
  latestKnownScheduleVersion,
  draftPatchCount,
  draftConflicts,
  clearDraft,
  triggerOptimization,
  isRunActive,
  activeRun,
  optimizeButtonFillWidth,
  uiStore,
  viewMode,
  setViewMode,
}: DashboardControlsProps) {
  return (
    <>
      <div className="flex justify-end">
        <div className="flex flex-wrap items-center justify-end gap-2">
          {hasNewerVersion ? (
            <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Newer schedule version detected on the backend.
              {latestKnownScheduleVersion > 0
                ? ` Latest version: ${latestKnownScheduleVersion}.`
                : null}
            </div>
          ) : null}
          {draftPatchCount > 0 ? (
            <button
              data-testid="revert-staged-changes"
              onClick={clearDraft}
              className="app-button-secondary min-h-9 whitespace-nowrap px-4 py-2"
              aria-label="Revert all draft changes"
            >
              Revert {draftPatchCount} staged
            </button>
          ) : null}
          <button
            data-testid="optimize-schedule"
            onClick={() => {
              void triggerOptimization();
            }}
            disabled={isRunActive}
            className="app-button-primary relative min-h-9 overflow-hidden whitespace-nowrap px-4 py-2"
            aria-label="Run schedule optimization"
          >
            {activeRun ? (
              <span
                aria-hidden="true"
                className="absolute inset-y-0 left-0 bg-gradient-to-r from-primary/40 via-primary/70 to-emerald-400/80 transition-[width] duration-300"
                style={{ width: optimizeButtonFillWidth }}
              />
            ) : null}
            <span className="relative z-10 flex items-center gap-2">
            <Zap size={16} />
            <span>{isRunActive ? "Optimizing..." : "Optimize"}</span>
            {activeRun ? <span className="text-xs">{activeRun.progressPercent}%</span> : null}
            </span>
          </button>
          <button
            data-testid="open-schedule-summary"
            onClick={uiStore.openSummaryModal}
            className="app-button-secondary min-h-9 whitespace-nowrap px-4 py-2"
            aria-label="View optimization summary"
          >
            <ListChecks size={16} />
            Summary
          </button>
          <button
            data-testid="open-scheduling-config"
            onClick={uiStore.openConfigModal}
            className="app-button-secondary min-h-9 whitespace-nowrap px-4 py-2"
            aria-label="Configure optimization settings"
          >
            <Settings size={16} />
            Configure
          </button>
          <div className="app-segmented flex space-x-1">
            <button
              data-testid="view-list"
              onClick={() => void setViewMode("list")}
              className={segmentedButtonVariants({
                size: "md",
                active: viewMode === "list",
              })}
            >
              <LayoutList size={14} /> <span>List</span>
            </button>
            <button
              data-testid="view-timeline"
              onClick={() => void setViewMode("timeline")}
              className={segmentedButtonVariants({
                size: "md",
                active: viewMode === "timeline",
              })}
            >
              <GanttChartSquare size={14} /> <span>Timeline</span>
            </button>
          </div>
        </div>
      </div>

      {activeRun ? (
        <div className="app-soft-panel flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm text-muted-foreground">
          <div>
            <span className="font-medium text-foreground">Run:</span> {activeRun.stage}
            {activeRun.statusMessage ? ` - ${activeRun.statusMessage}` : null}
          </div>
          <div>
            <span className="font-medium text-foreground">Progress:</span> {activeRun.progressPercent}%
          </div>
        </div>
      ) : null}

      {draftConflicts.length > 0 ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {draftConflicts.length} staged change conflict{draftConflicts.length === 1 ? "" : "s"} need review.
        </div>
      ) : null}
    </>
  );
}
