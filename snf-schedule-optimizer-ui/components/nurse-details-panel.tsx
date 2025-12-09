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
        ${selectedNurse ? "w-full md:w-80 border-l p-6 bg-gray-50" : "w-0 overflow-hidden"}
        flex flex-col transition-all duration-300 ease-in-out`}
    >
      {selectedNurse ? (
        <>
          <div className="flex justify-between items-start mb-4">
            <h4 className="text-2xl font-bold text-indigo-700">
              {selectedNurse.name}
            </h4>
            <button
              onClick={closeNurseDetails}
              className="p-1 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition"
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

          <div className="mb-6 p-4 bg-white rounded-lg shadow-md">
            <p className="font-semibold text-gray-700 mb-2">
              Scheduling Rationale:
            </p>
            <p className="text-sm text-gray-600 italic">
              {selectedNurse.schedulingRationale}
            </p>
          </div>

          <p className="text-lg font-semibold mb-4">Shift Control</p>

          {/* Control Buttons (These will eventually trigger Connect-ES mutations via the hook) */}
          <div className="space-y-3">
            <button
              onClick={() => removeNurseFromShift(selectedNurse)}
              className="w-full py-3 bg-red-600 text-white font-bold rounded-lg hover:bg-red-700 transition shadow-md active:shadow-none"
            >
              Remove from Shift ({selectedNurse.shiftHours} hrs)
            </button>

            <button
              onClick={addNurseToShift}
              className="w-full py-3 bg-indigo-600 text-white font-bold rounded-lg hover:bg-indigo-700 transition shadow-md active:shadow-none"
            >
              Add Available Nurse... (Mock)
            </button>
          </div>

          <div className="mt-auto pt-4 text-xs text-gray-500 border-t">
            <p>Nurse ID: {selectedNurse.id}</p>
          </div>
        </>
      ) : (
        <div className="h-full flex items-center justify-center text-center text-gray-500 italic">
          Select a nurse on the left to view details and controls.
        </div>
      )}
    </div>
  );
}
