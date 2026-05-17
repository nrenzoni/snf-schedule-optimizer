import React from "react";
import { format } from "date-fns";
import {
  Activity,
  ChevronLeft,
  ChevronRight,
  DollarSign,
  LayoutList,
  RotateCcw,
} from "lucide-react";
import { iconButtonVariants, segmentedButtonVariants } from "@/components/ui/styles";
import { UIDraftState } from "@/types/scheduling";
import { SimulatedUnit, ViewMode } from "@/types/scheduler";

interface BoardHeaderProps {
  visibleDates: Date[];
  pageSchedule: (dayDelta: number) => void;
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  groupingMode: "ROLE" | "BUDGET";
  setGroupingMode: (mode: "ROLE" | "BUDGET") => void;
  clearDraft: () => void;
  draftState: UIDraftState;
  units: SimulatedUnit[];
  handleCollapseAll: () => void;
  handleExpandAll: () => void;
  dragDisabled: boolean;
  activeRun: { progressPercent: number; statusMessage?: string } | null;
}

const VISIBLE_DAY_COUNT = 6;

export default function BoardHeader({
  visibleDates,
  pageSchedule,
  viewMode,
  setViewMode,
  groupingMode,
  setGroupingMode,
  clearDraft,
  draftState,
}: BoardHeaderProps) {
  return (
    <div className="z-50 flex items-center justify-between border-b border-border bg-card px-4 py-3">
      <div className="flex items-center gap-3">
        <h2 className="flex items-center gap-2 font-semibold text-foreground">
          <LayoutList size={18} className="text-primary" /> Master Schedule
        </h2>
        <div className="app-segmented flex items-center gap-1 p-1">
          <button
            type="button"
            onClick={() => pageSchedule(-VISIBLE_DAY_COUNT)}
            className={iconButtonVariants({ tone: "default" })}
            aria-label="Show previous 6 days"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="px-2 text-xs font-medium text-muted-foreground">
            {format(visibleDates[0], "MMM d")} - {format(visibleDates[VISIBLE_DAY_COUNT - 1], "MMM d")}
          </span>
          <button
            type="button"
            onClick={() => pageSchedule(VISIBLE_DAY_COUNT)}
            className={iconButtonVariants({ tone: "default" })}
            aria-label="Show next 6 days"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={clearDraft}
          disabled={draftState.patches.length === 0}
          className={iconButtonVariants({ tone: "soft", disabled: draftState.patches.length === 0 })}
          aria-label="Revert staged changes"
        >
          <RotateCcw size={14} />
        </button>
        <div className="app-segmented flex items-center text-xs font-bold">
          <span className="px-2 text-slate-500">Sub-Group:</span>
          <button
            onClick={() => setGroupingMode("ROLE")}
            className={segmentedButtonVariants({ size: "sm", active: groupingMode === "ROLE" })}
            aria-pressed={groupingMode === "ROLE"}
          >
            Role
          </button>
          <button
            onClick={() => setGroupingMode("BUDGET")}
            className={segmentedButtonVariants({ size: "sm", active: groupingMode === "BUDGET" })}
            aria-pressed={groupingMode === "BUDGET"}
          >
            Budget
          </button>
        </div>
        <div className="app-segmented flex items-center text-xs font-bold">
          <span className="px-2 text-slate-500">Metric:</span>
          <button
            onClick={() => setViewMode("ROLE")}
            className={segmentedButtonVariants({ size: "sm", active: viewMode === "ROLE" })}
            aria-pressed={viewMode === "ROLE"}
          >
            <Activity size={12} /> HPRD
          </button>
          <button
            onClick={() => setViewMode("BUDGET")}
            className={segmentedButtonVariants({ size: "sm", active: viewMode === "BUDGET" })}
            aria-pressed={viewMode === "BUDGET"}
          >
            <DollarSign size={12} /> Cost
          </button>
        </div>
      </div>
    </div>
  );
}
export default React.memo(BoardHeader);
