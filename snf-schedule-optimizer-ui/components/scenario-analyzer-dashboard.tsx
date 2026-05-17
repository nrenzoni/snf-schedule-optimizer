import React, { useState } from "react";
import { match } from "ts-pattern";
import {
  ArrowRight,
  Play,
  TrendingUp,
} from "lucide-react";
import { ModalType } from "@/types/modal-type";
import SimulationConfigModal from "@/components/modals/simulation-config-modal";
import SimulationResults from "@/components/simulation-results";

interface WageImpactParams {
  wageIncrease: string;
}

interface CensusImpactParams {
  censusChange: number;
}

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface AgencyReductionParams {
}

type SimulationParams =
  | WageImpactParams
  | CensusImpactParams
  | AgencyReductionParams;

// 2. Define the interface for the modalConfig state
interface ModalConfig {
  isOpen: boolean;
  type: ModalType | null; // The type must be one of the defined modal-type.ts strings or null
}

interface SimulationResult {
  name: string;
  metrics: {
    costImpact: string;
    projectedTotal: string;
    variance: string;
    efficiency: string;
  };
  insight: string;
}

// --- COMPONENT: ScenarioAnalyzerDashboard (Existing) ---
export default function ScenarioAnalyzerDashboard() {
  const [modalConfig, setModalConfig] = useState<ModalConfig>({
    isOpen: false,
    type: null,
  });

  const [simulationResult, setSimulationResult] =
    useState<SimulationResult | null>(null);

  const openSimulation = (type: ModalType) =>
    setModalConfig({ isOpen: true, type });
  const closeSimulation = () =>
    setModalConfig((current) => ({ ...current, isOpen: false }));

  const runSimulation = (type: ModalType | null, params: SimulationParams) => {
    const result: SimulationResult = match(type)
      .with("WAGE_IMPACT", () => {
        const wageParams = params as WageImpactParams;
        const increase = parseFloat(wageParams.wageIncrease);
        const base = 1200000;
        const projected = base * (1 + increase / 100);

        return {
          name: `Wage Increase Impact (${wageParams.wageIncrease}%)`,
          metrics: {
            costImpact: `+${increase}%`,
            projectedTotal: `$${(projected / 1000000).toFixed(2)}M`,
            variance: `$${((projected - base) / 1000).toFixed(0)}k`,
            efficiency: "94.2%",
          },
          insight: `Increasing wages by ${wageParams.wageIncrease}% improves retention probability by estimated 12% but exceeds Q4 budget.`,
        };
      })
      .with("CENSUS_IMPACT", () => {
        const censusParams = params as CensusImpactParams;

        return {
          name: `Census Drop Analysis (${censusParams.censusChange})`,
          metrics: {
            costImpact: "-4%",
            projectedTotal: "$1.15M",
            variance: "-$50k",
            efficiency: "88.5%",
          },
          insight: `Dropping census by ${Math.abs(censusParams.censusChange)} residents spikes HPPD to 4.2, suggesting overstaffing unless shifts are cut.`,
        };
      })
      .with("AGENCY_REDUCTION", () => {
        return {
          name: "Agency Reduction Plan",
          metrics: {
            costImpact: "-8%",
            projectedTotal: "$1.10M",
            variance: "-$100k",
            efficiency: "98.1%",
          },
          insight:
            "Converting 50% of agency usage to internal OT yields significant savings.",
        };
      })
      .with(null, () => ({
        name: "",
        metrics: {
          costImpact: "",
          projectedTotal: "",
          variance: "",
          efficiency: "",
        },
        insight: "",
      }))
      .exhaustive();

    setSimulationResult(result);
  };

  return (
    <div className="space-y-3 xl:my-auto">
      <div className="grid gap-3 lg:grid-cols-3">
        {/* Simulation Launcher */}
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
              aria-label="Run wage impact simulation"
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
              aria-label="Run census volatility simulation"
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
              aria-label="Run agency reduction simulation"
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

        {/* Main Content Area (Results or Placeholder) */}
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

      {/* Modal for Configuration */}
      <SimulationConfigModal
        type={modalConfig.type}
        isOpen={modalConfig.isOpen}
        onClose={closeSimulation}
        onRun={runSimulation}
      />
    </div>
  );
}
