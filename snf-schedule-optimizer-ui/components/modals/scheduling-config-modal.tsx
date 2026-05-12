import React, { useState } from "react";
import {
  AlertTriangle,
  Clock,
  DollarSign,
  Settings,
  Sliders,
  X,
} from "lucide-react";
import ModalContainer from "@/components/modal-container";

interface SchedulingSettings {
  useMLForecast: boolean;
  useCalloutBuffer: boolean;
  bufferThreshold: number; // Percentage, 0-100
  minRestPeriod: number; // Hours
  maxShiftLength: number; // Hours
  premiumWeekend: boolean;
  premiumHoliday: boolean;
  // Add any other setting properties here
}

interface SchedulingConfigModalProps {
  settings: SchedulingSettings;
  isOpen: boolean;
  onClose: () => void;
  // onUpdate takes a key (string) and a value (could be boolean, number, or string) and returns nothing.
  onUpdate: (
    key: keyof SchedulingSettings,
    value: SchedulingSettings[keyof SchedulingSettings],
  ) => void;
}

export function SchedulingConfigModal({
  settings,
  isOpen,
  onClose,
  onUpdate,
}: SchedulingConfigModalProps) {
  // Internal state for unsaved changes (kept for form management)
  const [draftSettings, setDraftSettings] =
    useState<SchedulingSettings>(settings);

  const handleUpdate = (
    key: keyof SchedulingSettings,
    value: SchedulingSettings[keyof SchedulingSettings],
  ) => {
    setDraftSettings((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    // Apply changes to the parent state
    // Object.keys(draftSettings) is automatically typed as (keyof SchedulingSettings)[]
    // because draftSettings is typed as SchedulingSettings.
    (Object.keys(draftSettings) as (keyof SchedulingSettings)[]).forEach(
      (key) => {
        onUpdate(key, draftSettings[key]);
      },
    );
    onClose();
  };

  return (
    <ModalContainer
      isOpen={isOpen}
      onClose={onClose}
      contentClassName="max-w-2xl"
    >
      {/* 2. Content starts directly with the modal's main content div,
               which no longer needs external transition classes. */}
      <div className="bg-white rounded-xl shadow-2xl w-full overflow-hidden">
        {/* HEADER */}
        <div className="border-b p-4 flex justify-between items-center bg-indigo-50">
          <div className="flex items-center space-x-2 text-indigo-800">
            <Settings size={20} />
            <h3 className="font-bold text-xl">Scheduler Configuration</h3>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1 rounded-full"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-8 max-h-[80vh] overflow-y-auto">
          <h4 className="text-lg font-semibold text-gray-700 border-b pb-2">
            Staffing & ML Integration
          </h4>
          <div className="grid md:grid-cols-2 gap-8">
            {/* 1. HPPD ML Forecast */}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border">
              <div>
                <label className="text-sm font-bold text-gray-800">
                  Factor in HPPD ML Forecast
                </label>
                <p className="text-xs text-gray-500">
                  Adjust staffing based on AI predictions
                </p>
              </div>
              <button
                onClick={() =>
                  setDraftSettings((prev) => ({
                    ...prev,
                    useMLForecast: !prev.useMLForecast,
                  }))
                }
                type="button"
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${draftSettings.useMLForecast ? "bg-indigo-600" : "bg-gray-200"}`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${draftSettings.useMLForecast ? "translate-x-6" : "translate-x-1"}`}
                />
              </button>
            </div>

            {/* 2. Call-out Buffer Toggle */}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border">
              <div>
                <label className="text-sm font-bold text-gray-800">
                  Include Call-out Buffer
                </label>
                <p className="text-xs text-gray-500">
                  Reserve extra staff for high-risk shifts
                </p>
              </div>
              <button
                onClick={() =>
                  setDraftSettings((prev) => ({
                    ...prev,
                    useCalloutBuffer: !prev.useCalloutBuffer,
                  }))
                }
                type="button"
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${draftSettings.useCalloutBuffer ? "bg-green-600" : "bg-gray-200"}`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${draftSettings.useCalloutBuffer ? "translate-x-6" : "translate-x-1"}`}
                />
              </button>
            </div>

            {/* 3. Buffer Threshold Slider */}
            <div
              className={`space-y-3 p-3 rounded-lg border ${!draftSettings.useCalloutBuffer ? "opacity-50 pointer-events-none bg-gray-100" : "bg-white"}`}
            >
              <div className="flex justify-between items-center">
                <label className="text-sm font-bold text-gray-800 flex items-center gap-2">
                  <Sliders size={16} /> Buffer Threshold
                </label>
                <span className="text-sm font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-1 rounded">
                  {draftSettings.bufferThreshold}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="20"
                value={draftSettings.bufferThreshold}
                onChange={(e) =>
                  handleUpdate("bufferThreshold", parseInt(e.target.value))
                }
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                disabled={!draftSettings.useCalloutBuffer}
              />
              <p className="text-xs text-gray-500">
                Percentage of shift capacity to hold as reserve.
              </p>
            </div>
          </div>

          <h4 className="text-lg font-semibold text-gray-700 border-b pb-2 pt-4">
            Compliance & Shift Rules
          </h4>
          <div className="grid md:grid-cols-2 gap-8">
            {/* 4. Min Rest Period */}
            <div className="space-y-3 p-3 bg-white rounded-lg border">
              <label className="text-sm font-bold text-gray-800 flex items-center gap-2">
                <Clock size={16} /> Minimum Rest Period (Hours)
              </label>
              <input
                type="number"
                min="8"
                max="16"
                step="1"
                value={draftSettings.minRestPeriod}
                onChange={(e) =>
                  handleUpdate("minRestPeriod", parseInt(e.target.value))
                }
                className="w-full border rounded-lg p-2 text-lg font-bold"
              />
              <p className="text-xs text-gray-500">
                Enforce minimum rest time between shifts (Current:{" "}
                {draftSettings.minRestPeriod} hrs).
              </p>
            </div>

            {/* 5. Max Shift Length */}
            <div className="space-y-3 p-3 bg-white rounded-lg border">
              <label className="text-sm font-bold text-gray-800 flex items-center gap-2">
                <AlertTriangle size={16} /> Maximum Shift Length (Hours)
              </label>
              <input
                type="number"
                min="8"
                max="14"
                step="0.5"
                value={draftSettings.maxShiftLength}
                onChange={(e) =>
                  handleUpdate("maxShiftLength", parseFloat(e.target.value))
                }
                className="w-full border rounded-lg p-2 text-lg font-bold"
              />
              <p className="text-xs text-gray-500">
                Prevent burnout/fatigue by limiting shift duration (Current:{" "}
                {draftSettings.maxShiftLength} hrs).
              </p>
            </div>

            {/* 6. Premium Shift Criteria */}
            <div className="md:col-span-2 space-y-3 p-3 bg-white rounded-lg border">
              <label className="text-sm font-bold text-gray-800 flex items-center gap-2">
                <DollarSign size={16} /> Premium Shift Criteria
              </label>
              <div className="flex space-x-4">
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={draftSettings.premiumWeekend}
                    onChange={(e) =>
                      handleUpdate("premiumWeekend", e.target.checked)
                    }
                    className="rounded text-indigo-600"
                  />
                  <label className="text-sm text-gray-700">
                    Weekend Shifts
                  </label>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={draftSettings.premiumHoliday}
                    onChange={(e) =>
                      handleUpdate("premiumHoliday", e.target.checked)
                    }
                    className="rounded text-indigo-600"
                  />
                  <label className="text-sm text-gray-700">
                    Holiday Shifts
                  </label>
                </div>
              </div>
              <p className="text-xs text-gray-500">
                Shifts matching selected criteria will be flagged for premium
                pay/priority scheduling.
              </p>
            </div>
          </div>
        </div>

        <div className="bg-gray-50 p-4 rounded-b-xl flex justify-end space-x-3 border-t">
          <button
            onClick={() => {
              setDraftSettings(settings);
              onClose();
            }}
            className="px-4 py-2 text-gray-600 hover:bg-gray-200 rounded-lg"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow-md transition"
          >
            Save & Apply Settings
          </button>
        </div>
      </div>
    </ModalContainer>
  );
}
