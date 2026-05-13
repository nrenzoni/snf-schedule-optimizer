import React, { useState } from "react";
import {
  Activity,
  ArrowRight,
  DollarSign,
  LucideIcon,
  PieChart,
  Play,
  TrendingUp,
  Users,
} from "lucide-react";
import { ModalType } from "@/types/modal-type";
import SimulationConfigModal from "@/components/modals/simulation-config-modal";
import SimulationResults from "@/components/simulation-results";

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

  interface WageImpactParams {
    wageIncrease: string; // Used as a string and parsed to float inside the function
  }

  interface CensusImpactParams {
    censusChange: number; // Used as a number
  }

  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface AgencyReductionParams {
    // Maybe an empty object, or specific props like 'targetReductionPercent: number'
  }

  type SimulationParams =
    | WageImpactParams
    | CensusImpactParams
    | AgencyReductionParams;

  const [simulationResult, setSimulationResult] =
    useState<SimulationResult | null>(null);

  const openSimulation = (type: ModalType) =>
    setModalConfig({ isOpen: true, type });
  const closeSimulation = () =>
    setModalConfig((current) => ({ ...current, isOpen: false }));

  const runSimulation = (type: ModalType | null, params: SimulationParams) => {

    // Mock calculation logic for demo purposes
    let result: SimulationResult = {
      name: "",
      metrics: {
        costImpact: "",
        projectedTotal: "",
        variance: "",
        efficiency: "",
      },
      insight: "",
    };

    if (type === "WAGE_IMPACT") {
      const wageParams = params as WageImpactParams;
      const increase = parseFloat(wageParams.wageIncrease);
      const base = 1200000;
      const projected = base * (1 + increase / 100);

      result = {
        name: `Wage Increase Impact (${wageParams.wageIncrease}%)`,
        metrics: {
          costImpact: `+${increase}%`,
          projectedTotal: `$${(projected / 1000000).toFixed(2)}M`,
          variance: `$${((projected - base) / 1000).toFixed(0)}k`,
          efficiency: "94.2%",
        },
        insight: `Increasing wages by ${wageParams.wageIncrease}% improves retention probability by estimated 12% but exceeds Q4 budget.`,
      };
    } else if (type === "CENSUS_IMPACT") {
      // Confirm type locally for safe access
      const censusParams = params as CensusImpactParams;

      result = {
        name: `Census Drop Analysis (${censusParams.censusChange})`,
        metrics: {
          costImpact: "-4%",
          projectedTotal: "$1.15M",
          variance: "-$50k",
          efficiency: "88.5%",
        },
        insight: `Dropping census by ${Math.abs(censusParams.censusChange)} residents spikes HPPD to 4.2, suggesting overstaffing unless shifts are cut.`,
      };
    } else if (type === "AGENCY_REDUCTION") {
      result = {
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
    }

    setSimulationResult(result);
  };

  const metrics = [
    {
      label: "Total Labor Spend (MTD)",
      value: "$142,500",
      trend: "+4.2%",
      icon: DollarSign,
      color: "text-primary",
      trendColor: "text-red-500",
    },
    {
      label: "Agency Utilization",
      value: "18.5%",
      trend: "-2.1%",
      icon: Users,
      color: "text-primary",
      trendColor: "text-green-600",
    },
    {
      label: "Avg HPPD",
      value: "3.82",
      trend: "Target: 3.6",
      icon: Activity,
      color: "text-primary",
      trendColor: "text-muted-foreground",
    },
    {
      label: "Overtime %",
      value: "8.4%",
      trend: "Target: <5%",
      icon: PieChart,
      color: "text-amber-600",
      trendColor: "text-amber-600",
    },
  ];

  const typedMetrics: Array<
    (typeof metrics)[number] & {
      icon: LucideIcon;
    }
  > = metrics;

  return (
    <div className="mx-auto max-w-6xl space-y-3">
      {/* Header / KPI Cards */}
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-4">
        {typedMetrics.map((kpi, idx) => (
          <div
            key={idx}
            className="app-card flex flex-col justify-between p-3 transition hover:border-primary/40"
          >
            <div className="mb-1.5 flex items-start justify-between">
              <span className="text-xs font-black uppercase tracking-[0.16em] text-slate-400">
                {kpi.label}
              </span>
              <kpi.icon size={18} className={kpi.color} />
            </div>
            <div>
              <span className="app-title text-xl">
                {kpi.value}
              </span>
              <span className={`text-xs ml-2 font-medium ${kpi.trendColor}`}>
                {kpi.trend}
              </span>
            </div>
          </div>
        ))}
      </div>

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
