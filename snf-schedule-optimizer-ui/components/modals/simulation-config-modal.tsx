import { Activity, Play, X } from "lucide-react";
import React, { useState } from "react";
import { ModalType } from "@/types/modal-type";
import ModalContainer from "../modal-container";

interface SimulationConfigModalProps {
  type: ModalType | null;
  isOpen: boolean;
  onClose: () => void; // Function that takes no arguments and returns nothing
  onRun: (
    type: ModalType | null,
    params: {
      // Function that takes the simulation parameters
      wageIncrease: number;
      targetAgencyReduction: number;
      censusChange: number;
      otCap: number;
    },
  ) => void; // and returns nothing
}

// --- COMPONENT: SimulationConfigModal (Scenario Analyzer Modal) ---
export default function SimulationConfigModal({
  type,
  isOpen,
  onClose,
  onRun,
}: SimulationConfigModalProps) {
  const [params, setParams] = useState({
    wageIncrease: 5,
    targetAgencyReduction: 50,
    censusChange: -10,
    otCap: 2,
  });

  const handleRun = () => {
    onRun(type, params);
    onClose();
  };

  let title = "Configure Simulation";
  let content = null;

  if (type === "WAGE_IMPACT") {
    title = "Wage Sensitivity Analysis";
    content = (
      <div className="space-y-4">
        <p className="text-sm text-slate-500">
          Project the impact of across-the-board wage increases on the annual
          budget.
        </p>
        <div>
          <label className="mb-1 block text-sm font-bold text-slate-700">
            Proj. Wage Increase (%)
          </label>
          <input
            type="range"
            min="0"
            max="20"
            step="0.5"
            value={params.wageIncrease}
            onChange={(e) =>
              setParams({ ...params, wageIncrease: Number(e.target.value) })
            }
            className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-indigo-600"
          />
          <div className="mt-1 flex justify-between text-xs text-slate-500">
            <span>0%</span>
            <span className="text-lg font-semibold text-[#168039]">
              {params.wageIncrease}%
            </span>
            <span>20%</span>
          </div>
        </div>
      </div>
    );
  } else if (type === "AGENCY_REDUCTION") {
    title = "Agency Utilization Strategy";
    content = (
      <div className="space-y-4">
        <p className="text-sm text-slate-500">
          Analyze savings by converting agency hours to internal overtime or new
          hires.
        </p>
        <div>
          <label className="mb-1 block text-sm font-bold text-slate-700">
            Target Reduction in Agency Hours (%)
          </label>
          <input
            type="number"
            value={params.targetAgencyReduction}
            onChange={(e) =>
              setParams({
                ...params,
                targetAgencyReduction: Number(e.target.value),
              })
            }
            className="app-input w-full"
          />
        </div>
      </div>
    );
  } else if (type === "CENSUS_IMPACT") {
    title = "Census Volatility Modeling";
    content = (
      <div className="space-y-4">
        <p className="text-sm text-slate-500">
          Calculate HPPD and labor cost per patient day (PPD) based on census
          shifts.
        </p>
        <div>
          <label className="mb-1 block text-sm font-bold text-slate-700">
            Projected Census Change (Residents)
          </label>
          <div className="flex items-center space-x-2">
            <input
              type="number"
              value={params.censusChange}
              onChange={(e) =>
                setParams({ ...params, censusChange: Number(e.target.value) })
              }
              className="app-input w-full"
            />
            <span className="text-sm text-slate-500">residents</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    // 1. Replaced the entire backdrop div with ModalContainer
    <ModalContainer
      isOpen={isOpen}
      onClose={onClose}
      contentClassName="max-w-md"
    >
      {/* 2. Content starts directly with the modal's main content div */}
      <div className="w-full bg-white/80">
        {/* HEADER */}
        <div className="flex items-center justify-between border-b border-[#E0E0E0] bg-white p-4">
          <div className="flex items-center space-x-2 text-[#168039]">
            {/* Assuming Activity, title, and X are available via props/imports */}
            <Activity size={20} />
            <h3 className="text-lg font-semibold">{title}</h3>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1 text-slate-400 hover:bg-white/80 hover:text-slate-700"
          >
            <X size={20} />
          </button>
        </div>

        {/* BODY / CONTENT */}
        <div className="p-6">
          {content} {/* Dynamic content is rendered here */}
        </div>

        {/* FOOTER / ACTIONS */}
        <div className="flex justify-end space-x-3 border-t border-slate-200/70 bg-slate-50/80 p-4">
          <button
            onClick={onClose}
            className="app-button-ghost"
          >
            Cancel
          </button>
          <button
            data-testid="run-simulation"
            onClick={handleRun}
            className="app-button-primary"
          >
            <Play size={16} fill="currentColor" />
            <span>Run Simulation</span>
          </button>
        </div>
      </div>
    </ModalContainer>
  );
}
