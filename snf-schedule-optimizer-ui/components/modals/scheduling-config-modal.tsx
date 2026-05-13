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
import {
  iconButtonVariants,
  toggleThumbVariants,
  toggleTrackVariants,
} from "@/components/ui/styles";
import { cn } from "@/lib/utils";
import { UISchedulerSettings } from "@/types/scheduling";

interface SchedulingConfigModalProps {
  settings: UISchedulerSettings;
  isOpen: boolean;
  onClose: () => void;
  onUpdate: (settings: UISchedulerSettings) => void;
}

export function SchedulingConfigModal({
  settings,
  isOpen,
  onClose,
  onUpdate,
}: SchedulingConfigModalProps) {
  // Internal state for unsaved changes (kept for form management)
  const [draftSettings, setDraftSettings] = useState<UISchedulerSettings>(settings);

  const handleUpdate = (
    key: keyof UISchedulerSettings,
    value: UISchedulerSettings[keyof UISchedulerSettings],
  ) => {
    setDraftSettings((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    onUpdate(draftSettings);
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
      <div className="w-full overflow-hidden bg-white/82">
        {/* HEADER */}
        <div className="app-modal-header">
          <div className="flex items-center space-x-2 text-primary">
            <Settings size={20} />
            <h3 className="text-xl font-black">Scheduler Configuration</h3>
          </div>
          <button
            onClick={onClose}
            className={iconButtonVariants({ shape: "full", tone: "default" })}
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-8 max-h-[80vh] overflow-y-auto">
          <h4 className="border-b border-slate-200/70 pb-2 text-lg font-black text-slate-800">
            Staffing & ML Integration
          </h4>
          <div className="grid md:grid-cols-2 gap-8">
            {/* 1. HPPD ML Forecast */}
            <div className="app-soft-panel flex items-center justify-between p-3">
              <div>
                <label className="text-sm font-bold text-slate-800">
                  Factor in HPPD ML Forecast
                </label>
                <p className="text-xs text-slate-500">
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
                className={toggleTrackVariants({ checked: draftSettings.useMLForecast })}
              >
                <span
                  className={toggleThumbVariants({ checked: draftSettings.useMLForecast })}
                />
              </button>
            </div>

            {/* 2. Call-out Buffer Toggle */}
            <div className="app-soft-panel flex items-center justify-between p-3">
              <div>
                <label className="text-sm font-bold text-slate-800">
                  Include Call-out Buffer
                </label>
                <p className="text-xs text-slate-500">
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
                className={toggleTrackVariants({ checked: draftSettings.useCalloutBuffer })}
              >
                <span
                  className={toggleThumbVariants({ checked: draftSettings.useCalloutBuffer })}
                />
              </button>
            </div>

            {/* 3. Buffer Threshold Slider */}
            <div
                className={cn(
                  "space-y-3 rounded-lg border border-border p-3",
                  !draftSettings.useCalloutBuffer
                    ? "pointer-events-none bg-background opacity-50"
                    : "bg-card",
                )}
            >
              <div className="flex justify-between items-center">
                <label className="flex items-center gap-2 text-sm font-bold text-slate-800">
                  <Sliders size={16} /> Buffer Threshold
                </label>
              <span className="rounded bg-accent px-2 py-1 font-mono text-sm font-medium text-primary">
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
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-indigo-600"
                disabled={!draftSettings.useCalloutBuffer}
              />
              <p className="text-xs text-slate-500">
                Percentage of shift capacity to hold as reserve.
              </p>
            </div>
          </div>

          <h4 className="border-b border-slate-200/70 pb-2 pt-4 text-lg font-black text-slate-800">
            Compliance & Shift Rules
          </h4>
          <div className="grid md:grid-cols-2 gap-8">
            {/* 4. Min Rest Period */}
            <div className="space-y-3 rounded-lg border border-border bg-card p-3">
              <label className="flex items-center gap-2 text-sm font-bold text-slate-800">
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
                className="app-input w-full text-lg"
              />
              <p className="text-xs text-slate-500">
                Enforce minimum rest time between shifts (Current:{" "}
                {draftSettings.minRestPeriod} hrs).
              </p>
            </div>

            {/* 5. Max Shift Length */}
            <div className="space-y-3 rounded-lg border border-border bg-card p-3">
              <label className="flex items-center gap-2 text-sm font-bold text-slate-800">
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
                className="app-input w-full text-lg"
              />
              <p className="text-xs text-slate-500">
                Prevent burnout/fatigue by limiting shift duration (Current:{" "}
                {draftSettings.maxShiftLength} hrs).
              </p>
            </div>

            {/* 6. Premium Shift Criteria */}
            <div className="space-y-3 rounded-lg border border-border bg-card p-3 md:col-span-2">
              <label className="flex items-center gap-2 text-sm font-bold text-slate-800">
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
                    className="rounded text-primary"
                  />
                  <label className="text-sm text-slate-700">
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
                    className="rounded text-primary"
                  />
                  <label className="text-sm text-slate-700">
                    Holiday Shifts
                  </label>
                </div>
              </div>
              <p className="text-xs text-slate-500">
                Shifts matching selected criteria will be flagged for premium
                pay/priority scheduling.
              </p>
            </div>

            <div className="space-y-3 rounded-lg border border-border bg-card p-3 md:col-span-2">
              <label className="flex items-center gap-2 text-sm font-bold text-slate-800">
                <DollarSign size={16} /> Optimization Penalties
              </label>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="text-xs font-semibold text-slate-500">
                    Overtime Avoidance
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="50"
                    value={draftSettings.overtimeAvoidancePenalty}
                    onChange={(e) =>
                      handleUpdate("overtimeAvoidancePenalty", parseFloat(e.target.value))
                    }
                    className="app-input mt-1 w-full"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500">
                    Team Consistency
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="25"
                    value={draftSettings.teamConsistencyPenalty}
                    onChange={(e) =>
                      handleUpdate("teamConsistencyPenalty", parseFloat(e.target.value))
                    }
                    className="app-input mt-1 w-full"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500">
                    High-Risk Shift
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="50"
                    value={draftSettings.highRiskShiftPenalty}
                    onChange={(e) =>
                      handleUpdate("highRiskShiftPenalty", parseFloat(e.target.value))
                    }
                    className="app-input mt-1 w-full"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500">
                    Custom Preference
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="50"
                    value={draftSettings.customPreferencePenalty}
                    onChange={(e) =>
                      handleUpdate("customPreferencePenalty", parseFloat(e.target.value))
                    }
                    className="app-input mt-1 w-full"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="app-modal-footer">
          <button
            onClick={() => {
              setDraftSettings(settings);
              onClose();
            }}
            className="app-button-ghost"
          >
            Cancel
          </button>
          <button
            data-testid="save-scheduling-config"
            onClick={handleSave}
            className="app-button-primary"
          >
            Save & Apply Settings
          </button>
        </div>
      </div>
    </ModalContainer>
  );
}
