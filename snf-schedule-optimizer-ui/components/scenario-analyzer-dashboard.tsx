import { useState } from "react";
import {
  ArrowRight,
  Play,
  TrendingUp,
} from "lucide-react";
import { ModalType } from "@/types/modal-type";
import SimulationConfigModal from "@/components/modals/simulation-config-modal";
import SimulationResults from "@/components/simulation-results";
import useSimulationRunner from "@/hooks/use-simulation-runner";
import type { ModalConfig } from "@/hooks/use-simulation-runner";

export default function ScenarioAnalyzerDashboard() {
  const [modalConfig, setModalConfig] = useState<ModalConfig>({
    isOpen: false,
    type: null,
  });

  const { simulationResult, runSimulation, setSimulationResult } =
    useSimulationRunner();

  const openSimulation = (type: ModalType) =>
    setModalConfig({ isOpen: true, type });
  const closeSimulation = () =>
    setModalConfig((current) => ({ ...current, isOpen: false }));

  return (
    <div className="space-y-3 xl:my-auto">
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="app-card p-4 lg:col-span-1">
          <h3 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
            <Play size={18} className="text-primary" />
            Run New Simulation
          </h3>
          <div className="space-y-2">
            <button
              data-testid="simulation-wage-impact"
              onClick={() => openSimulation("WAGE_IMPACT")}
              className="group w-full rounded-lg border border-border bg-card p-3 text-left transition hover:border-primary/40 hover:bg-accent"
            >
              <div className="flex justify-between items-center">
                <span className="font-medium text-foreground group-hover:text-primary">
                  Wage Impact Analysis
                </span>
                <ArrowRight
                  size={16}
                  className="text-muted-foreground group-hover:text-primary"
                />
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Model budget changes vs rate hikes
              </p>
            </button>

            <button
              data-testid="simulation-census-impact"
              onClick={() => openSimulation("CENSUS_IMPACT")}
              className="group w-full rounded-lg border border-border bg-card p-3 text-left transition hover:border-primary/40 hover:bg-accent"
            >
              <div className="flex justify-between items-center">
                <span className="font-medium text-foreground group-hover:text-primary">
                  Census Volatility
                </span>
                <ArrowRight
                  size={16}
                  className="text-muted-foreground group-hover:text-primary"
                />
              </div>
              <p className="mt-1 text-xs text-slate-500">
                HPPD adjustments based on occupancy
              </p>
            </button>

            <button
              data-testid="simulation-agency-reduction"
              onClick={() => openSimulation("AGENCY_REDUCTION")}
              className="group w-full rounded-lg border border-border bg-card p-3 text-left transition hover:border-primary/40 hover:bg-accent"
            >
              <div className="flex justify-between items-center">
                <span className="font-medium text-foreground group-hover:text-primary">
                  Agency Reduction Strategy
                </span>
                <ArrowRight
                  size={16}
                  className="text-muted-foreground group-hover:text-primary"
                />
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Cost benefit of internal hiring
              </p>
            </button>
          </div>
        </div>

        <div className="lg:col-span-2">
          {simulationResult ? (
            <SimulationResults
              result={simulationResult}
              onClear={() => setSimulationResult(null)}
            />
          ) : (
            <div className="app-card flex h-full min-h-[300px] flex-col items-center justify-center border-dashed border-indigo-200/80 p-8 text-center">
              <div className="mb-4 rounded-lg bg-card p-4 shadow-sm">
                <TrendingUp size={32} className="text-primary" />
              </div>
              <h3 className="font-bold text-slate-700">
                No Active Simulation
              </h3>
              <p className="mt-2 max-w-xs text-sm text-slate-500">
                Select a simulation type from the left to model financial and
                operational scenarios.
              </p>
            </div>
          )}
        </div>
      </div>

      <SimulationConfigModal
        type={modalConfig.type}
        isOpen={modalConfig.isOpen}
        onClose={closeSimulation}
        onRun={runSimulation}
      />
    </div>
  );
}
