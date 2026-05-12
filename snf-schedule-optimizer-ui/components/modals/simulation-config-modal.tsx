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
        <p className="text-sm text-gray-500">
          Project the impact of across-the-board wage increases on the annual
          budget.
        </p>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
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
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>0%</span>
            <span className="font-bold text-indigo-600 text-lg">
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
        <p className="text-sm text-gray-500">
          Analyze savings by converting agency hours to internal overtime or new
          hires.
        </p>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
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
            className="w-full border rounded-lg p-2"
          />
        </div>
      </div>
    );
  } else if (type === "CENSUS_IMPACT") {
    title = "Census Volatility Modeling";
    content = (
      <div className="space-y-4">
        <p className="text-sm text-gray-500">
          Calculate HPPD and labor cost per patient day (PPD) based on census
          shifts.
        </p>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Projected Census Change (Residents)
          </label>
          <div className="flex items-center space-x-2">
            <input
              type="number"
              value={params.censusChange}
              onChange={(e) =>
                setParams({ ...params, censusChange: Number(e.target.value) })
              }
              className="w-full border rounded-lg p-2"
            />
            <span className="text-sm text-gray-500">residents</span>
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
      <div className="bg-white rounded-xl shadow-2xl w-full">
        {/* HEADER */}
        <div className="border-b p-4 flex justify-between items-center">
          <div className="flex items-center space-x-2 text-indigo-700">
            {/* Assuming Activity, title, and X are available via props/imports */}
            <Activity size={20} />
            <h3 className="font-bold text-lg">{title}</h3>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X size={20} />
          </button>
        </div>

        {/* BODY / CONTENT */}
        <div className="p-6">
          {content} {/* Dynamic content is rendered here */}
        </div>

        {/* FOOTER / ACTIONS */}
        <div className="bg-gray-50 p-4 rounded-b-xl flex justify-end space-x-3 border-t">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
          >
            Cancel
          </button>
          <button
            data-testid="run-simulation"
            onClick={handleRun}
            className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow-md transition"
          >
            <Play size={16} fill="currentColor" />
            <span>Run Simulation</span>
          </button>
        </div>
      </div>
    </ModalContainer>
  );
}
