import { useState } from "react";
import { match } from "ts-pattern";
import { ModalType } from "@/types/modal-type";

interface WageImpactParams {
  wageIncrease: string;
}

interface CensusImpactParams {
  censusChange: number;
}

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface AgencyReductionParams {}

type SimulationParams =
  | WageImpactParams
  | CensusImpactParams
  | AgencyReductionParams;

interface ModalConfig {
  isOpen: boolean;
  type: ModalType | null;
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

export default function useSimulationRunner() {
  const [simulationResult, setSimulationResult] =
    useState<SimulationResult | null>(null);

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

  return { simulationResult, runSimulation, setSimulationResult };
}

export type { SimulationResult, ModalConfig, SimulationParams };
