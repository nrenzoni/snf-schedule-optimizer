import React from "react";
import { UINurse } from "@/types/scheduling";

interface NurseDetailsPanelProps {
  selectedNurse: UINurse | null;
  closeNurseDetails: () => void;
  removeNurseFromShift: (nurse: UINurse) => Promise<void>;
  addNurseToShift: () => void;
}

export default function NurseDetailsPanel({
  selectedNurse,
  closeNurseDetails,
  removeNurseFromShift,
  addNurseToShift,
}: NurseDetailsPanelProps) {
  console.log("Rendering NurseDetailsPanel. Selected Nurse:", selectedNurse);

  return (
    <div
      className={`
        ${selectedNurse ? "w-full border-l border-[#E0E0E0] bg-[#F4F6F8] p-6 md:w-80" : "w-0 overflow-hidden"}
        flex flex-col transition-all duration-300 ease-in-out`}
    >
      {selectedNurse ? (
        <>
          <div className="mb-4 flex items-start justify-between">
            <h4 className="text-2xl font-semibold text-[#168039]">
              {selectedNurse.name}
            </h4>
            <button
              onClick={closeNurseDetails}
              className="rounded-lg p-1 text-[#6C757D] transition hover:bg-white hover:text-[#212529]"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M6 18L18 6M6 6l12 12"
                ></path>
              </svg>
            </button>
          </div>

          <div className="app-card-solid mb-6 p-4">
            <p className="mb-2 font-bold text-slate-700">
              Scheduling Rationale:
            </p>
            <p className="text-sm italic text-slate-600">
              {selectedNurse.schedulingRationale}
            </p>
          </div>

          <p className="mb-4 text-lg font-black text-slate-900">Shift Control</p>

          {/* Control Buttons (These will eventually trigger Connect-ES mutations via the hook) */}
          <div className="space-y-3">
            <button
              onClick={() => removeNurseFromShift(selectedNurse)}
              className="app-button-danger w-full py-3"
            >
              Remove from Shift ({selectedNurse.shiftHours} hrs)
            </button>

            <button
              onClick={addNurseToShift}
              className="app-button-primary w-full py-3"
            >
              Add Available Nurse... (Mock)
            </button>
          </div>

          <div className="mt-auto border-t border-slate-200/70 pt-4 text-xs text-slate-500">
            <p>Nurse ID: {selectedNurse.id}</p>
          </div>
        </>
      ) : (
        <div className="flex h-full items-center justify-center text-center italic text-slate-500">
          Select a nurse on the left to view details and controls.
        </div>
      )}
    </div>
  );
}
