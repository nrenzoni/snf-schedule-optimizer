import React from "react";
import { CheckCircle, Clock, DollarSign, ListChecks, Users, X } from "lucide-react";
import ModalContainer from "../modal-container";
import {
  iconButtonVariants,
  statPanelVariants,
  statValueVariants,
} from "@/components/ui/styles";
import { cn } from "@/lib/utils";
import {
  UIFinancials,
  UIOptimizationStats,
  UIOptimizationSummary,
  UISchedulerSettings,
} from "@/types/scheduling";

interface ScheduleSummaryModalProps {
  settings: UISchedulerSettings;
  optimizationSummary: UIOptimizationSummary | null;
  optimizationStats: UIOptimizationStats | null;
  optimizationFinancials: UIFinancials | null;
  isOpen: boolean;
  onClose: () => void;
}

export function ScheduleSummaryModal({
  settings,
  optimizationSummary,
  optimizationStats,
  optimizationFinancials,
  isOpen,
  onClose,
}: ScheduleSummaryModalProps) {
  const appliedSettings = optimizationSummary?.appliedSettings ?? settings;

  return (
    <ModalContainer isOpen={isOpen} onClose={onClose} contentClassName="max-w-5xl">
      <div className="w-full overflow-hidden bg-white/82">
        <div className="app-modal-header">
          <div className="flex items-center space-x-2">
            <ListChecks size={24} />
            <h3 className="text-xl font-black">Monthly Schedule Summary</h3>
          </div>
          <button onClick={onClose} className={iconButtonVariants({ tone: "soft" })}>
            <X size={20} />
          </button>
        </div>

        <div className="grid gap-8 p-6 lg:grid-cols-3 max-h-[80vh] overflow-y-auto">
          <div>
            <h4 className="mb-4 flex items-center gap-2 border-b border-border pb-2 text-lg font-semibold text-primary">
              <CheckCircle size={18} /> Operational
            </h4>
            <div className="space-y-3">
              <div className={statPanelVariants({ tone: "success" })}>
                <span className="font-medium text-slate-700">Covered Shifts</span>
                <span className="text-xl font-semibold text-primary">
                  {optimizationSummary?.coveredShifts ?? 0}
                </span>
              </div>
              <div className={cn("flex justify-between", statPanelVariants({ tone: "neutral" }))}>
                <span className="font-medium text-slate-700">Uncovered Shifts</span>
                <span className={statValueVariants({ tone: (optimizationSummary?.uncoveredShifts ?? 0) > 0 ? "warning" : "success" })}>
                  {optimizationSummary?.uncoveredShifts ?? 0}
                </span>
              </div>
              <div className={cn("flex justify-between", statPanelVariants({ tone: "neutral" }))}>
                <span className="font-medium text-slate-700">Assignments Changed</span>
                <span className="text-xl font-bold text-slate-800">
                  {optimizationSummary?.assignmentsChanged ?? 0}
                </span>
              </div>
              <div className={cn("flex justify-between", statPanelVariants({ tone: "neutral" }))}>
                <span className="font-medium text-slate-700">Min Rest</span>
                <span className="text-xl font-bold text-slate-800">
                  {appliedSettings.minRestPeriod} hrs
                </span>
              </div>
            </div>
          </div>

          <div>
            <h4 className="mb-4 flex items-center gap-2 border-b border-border pb-2 text-lg font-semibold text-primary">
              <DollarSign size={18} /> Financial
            </h4>
            <div className="space-y-3">
              <div className={statPanelVariants({ tone: "success" })}>
                <span className="font-medium text-slate-700">Projected Labor Cost</span>
                <span className="text-xl font-semibold text-primary">
                  ${Math.round(optimizationFinancials?.totalEnterpriseCost ?? 0).toLocaleString()}
                </span>
              </div>
              <div className={cn("flex justify-between", statPanelVariants({ tone: "neutral" }))}>
                <span className="font-medium text-slate-700">Overtime Cost</span>
                <span className="text-xl font-bold text-slate-800">
                  ${Math.round(optimizationFinancials?.totalOvertimeCost ?? 0).toLocaleString()}
                </span>
              </div>
              <div className={cn("flex justify-between", statPanelVariants({ tone: "neutral" }))}>
                <span className="font-medium text-slate-700">Incentive Cost</span>
                <span className="text-xl font-bold text-slate-800">
                  ${Math.round(optimizationFinancials?.totalIncentiveCost ?? 0).toLocaleString()}
                </span>
              </div>
              <div className={cn("flex justify-between", statPanelVariants({ tone: "neutral" }))}>
                <span className="font-medium text-slate-700">Regular Pay</span>
                <span className="text-xl font-bold text-slate-800">
                  ${Math.round(optimizationFinancials?.regularPayCost ?? 0).toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          <div>
            <h4 className="mb-4 flex items-center gap-2 border-b border-border pb-2 text-lg font-semibold text-primary">
              <Users size={18} /> Solver
            </h4>
            <div className="space-y-3">
              <div className={statPanelVariants({ tone: "success" })}>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 font-medium text-slate-700">
                    <Clock size={16} className="text-primary" /> Runtime
                  </span>
                  <span className="text-xl font-semibold text-primary">
                    {Math.round(optimizationStats?.executionTimeMs ?? 0)} ms
                  </span>
                </div>
              </div>
              <div className={cn("flex justify-between", statPanelVariants({ tone: "neutral" }))}>
                <span className="font-medium text-slate-700">Objective</span>
                <span className="text-xl font-bold text-slate-800">
                  {(optimizationStats?.objectiveValue ?? 0).toFixed(2)}
                </span>
              </div>
              <div className={cn("flex justify-between", statPanelVariants({ tone: "neutral" }))}>
                <span className="font-medium text-slate-700">Variables</span>
                <span className="text-xl font-bold text-slate-800">
                  {optimizationStats?.totalVariables ?? 0}
                </span>
              </div>
              <div className={cn("flex justify-between", statPanelVariants({ tone: "neutral" }))}>
                <span className="font-medium text-slate-700">Constraints</span>
                <span className="text-xl font-bold text-slate-800">
                  {optimizationStats?.totalConstraints ?? 0}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-border bg-muted/80 p-4">
          <p className="text-sm italic text-gray-500 pl-2">
            Latest run: {optimizationSummary?.completedAt ?? "No optimization completed yet."}
          </p>
          <button onClick={onClose} className="app-button-primary px-6">
            Close Summary
          </button>
        </div>
      </div>
    </ModalContainer>
  );
}
