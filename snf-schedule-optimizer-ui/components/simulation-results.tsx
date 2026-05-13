import React from "react";
import { AlertCircle, Download, FileText, X } from "lucide-react";
import { iconButtonVariants } from "@/components/ui/styles";

interface SimulationMetrics {
  costImpact: string; // Used in the Projected Bar
  projectedTotal: string; // Used in the Analysis Details table
  variance: string; // Used in the Analysis Details table
  efficiency: string; // Used in the Analysis Details table
}

interface SimulationResultData {
  name: string; // Used in the report header
  metrics: SimulationMetrics; // Contains the nested metrics
  insight: string; // Used in the Insight box
  // Add any other top-level properties of your simulation result here
}

interface SimulationResultsProps {
  result: SimulationResultData | null; // Can be null before data loads
  onClear: () => void; // Function to clear results
}

// --- COMPONENT: SimulationResults ---
export default function SimulationResults({
  result,
  onClear,
}: SimulationResultsProps) {
  if (!result) return null;

  return (
    <div className="app-card mt-8 overflow-hidden animate-in slide-in-from-bottom-4 duration-500">
      <div className="app-modal-header">
        <div>
          <h3 className="flex items-center gap-2 font-black text-slate-900">
            <FileText size={18} className="text-primary" />
            Simulation Report: {result.name}
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            Generated: {new Date().toLocaleString()}
          </p>
        </div>
        <div className="flex space-x-2">
          <button className={iconButtonVariants({ shape: "full", tone: "default" })}>
            <Download size={18} />
          </button>
          <button
            onClick={onClear}
            className={iconButtonVariants({ shape: "full", tone: "default" })}
          >
            <X size={18} />
          </button>
        </div>
      </div>

      <div className="grid gap-8 p-6 md:grid-cols-2">
        {/* Visual Representation (Mock Chart) */}
        <div className="space-y-4">
          <h4 className="text-sm font-black uppercase tracking-[0.16em] text-slate-500">
            Projected Impact
          </h4>
          <div className="flex h-48 items-end justify-around space-x-4 rounded-lg border border-dashed border-border bg-background p-4">
            {/* Current Bar */}
            <div
              className="group relative w-16 rounded-t-lg bg-input transition-all hover:bg-muted-foreground"
              style={{ height: "60%" }}
            >
              <div className="absolute -top-6 left-0 right-0 text-center text-xs font-bold text-slate-600">
                Current
              </div>
              <div className="absolute inset-0 flex items-end justify-center pb-2 opacity-0 group-hover:opacity-100 text-xs font-bold text-white transition-opacity">
                $1.2M
              </div>
            </div>
            {/* Projected Bar */}
            <div
              className="group relative w-16 rounded-t-lg bg-primary shadow-none transition-all hover:bg-primary/90"
              style={{ height: "85%" }}
            >
              <div className="absolute -top-6 left-0 right-0 text-center text-xs font-medium text-primary">
                Proj.
              </div>
              <div className="absolute inset-0 flex items-end justify-center pb-2 opacity-0 group-hover:opacity-100 text-xs font-bold text-white transition-opacity">
                {result.metrics.costImpact}
              </div>
            </div>
          </div>
          <p className="text-center text-sm italic text-slate-500">
            Visualizing annual cost variance
          </p>
        </div>

        {/* Key Metrics Table */}
        <div>
          <h4 className="mb-3 text-sm font-black uppercase tracking-[0.16em] text-slate-500">
            Analysis Details
          </h4>
          <div className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card">
            <div className="flex items-center justify-between p-3">
              <span className="text-slate-600">Base Labor Cost</span>
              <span className="font-mono font-medium">$1,200,000</span>
            </div>
            <div className="flex items-center justify-between bg-accent p-3">
              <span className="font-medium text-primary">
                Projected Cost
              </span>
              <span className="font-mono font-semibold text-primary">
                {result.metrics.projectedTotal}
              </span>
            </div>
            <div className="flex items-center justify-between p-3">
              <span className="text-slate-600">Variance</span>
              <span className="font-mono font-medium text-rose-500">
                {result.metrics.variance.startsWith("-")
                  ? result.metrics.variance
                  : `+${result.metrics.variance}`}
              </span>
            </div>
            <div className="flex items-center justify-between p-3">
              <span className="text-slate-600">Efficiency Score</span>
              <span className="font-mono font-medium">
                {result.metrics.efficiency}
              </span>
            </div>
          </div>

          <div className="app-callout-warning mt-4 flex items-start space-x-2 p-3 text-sm">
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
            <p>
              <strong>Insight:</strong> {result.insight}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
