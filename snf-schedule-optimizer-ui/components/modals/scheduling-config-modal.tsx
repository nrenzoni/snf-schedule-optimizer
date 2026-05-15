import React, { useEffect } from "react";
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
import { useForm, useWatch, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { schedulerSettingsSchema, SchedulerSettingsFormValues } from "@/lib/validation";

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
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<SchedulerSettingsFormValues>({
    resolver: zodResolver(schedulerSettingsSchema),
    defaultValues: settings,
  });

  useEffect(() => {
    reset(settings);
  }, [settings, reset]);

  const useCalloutBuffer = useWatch({ control, name: "useCalloutBuffer" });
  const bufferThreshold = useWatch({ control, name: "bufferThreshold" });
  const minRestPeriod = useWatch({ control, name: "minRestPeriod" });
  const maxShiftLength = useWatch({ control, name: "maxShiftLength" });

  const onSubmit = (data: SchedulerSettingsFormValues) => {
    onUpdate(data);
    onClose();
  };

  const handleCancel = () => {
    reset(settings);
    onClose();
  };

  return (
    <ModalContainer
      isOpen={isOpen}
      onClose={handleCancel}
      contentClassName="max-w-2xl"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="w-full overflow-hidden bg-white/82">
        <div className="app-modal-header">
          <div className="flex items-center space-x-2 text-primary">
            <Settings size={20} />
            <h3 className="text-xl font-black">Scheduler Configuration</h3>
          </div>
          <button
            type="button"
            onClick={handleCancel}
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
            <div className="app-soft-panel flex items-center justify-between p-3">
              <div>
                <label className="text-sm font-bold text-slate-800">
                  Factor in HPPD ML Forecast
                </label>
                <p className="text-xs text-slate-500">
                  Adjust staffing based on AI predictions
                </p>
              </div>
              <Controller
                name="useMLForecast"
                control={control}
                render={({ field }) => (
                  <button
                    type="button"
                    role="switch"
                    aria-checked={field.value}
                    onClick={() => field.onChange(!field.value)}
                    className={toggleTrackVariants({ checked: field.value })}
                  >
                    <span
                      className={toggleThumbVariants({ checked: field.value })}
                    />
                  </button>
                )}
              />
            </div>

            <div className="app-soft-panel flex items-center justify-between p-3">
              <div>
                <label className="text-sm font-bold text-slate-800">
                  Include Call-out Buffer
                </label>
                <p className="text-xs text-slate-500">
                  Reserve extra staff for high-risk shifts
                </p>
              </div>
              <Controller
                name="useCalloutBuffer"
                control={control}
                render={({ field }) => (
                  <button
                    type="button"
                    role="switch"
                    aria-checked={field.value}
                    onClick={() => field.onChange(!field.value)}
                    className={toggleTrackVariants({ checked: field.value })}
                  >
                    <span
                      className={toggleThumbVariants({ checked: field.value })}
                    />
                  </button>
                )}
              />
            </div>

            <div
              className={cn(
                "space-y-3 rounded-lg border border-border p-3",
                !useCalloutBuffer
                  ? "pointer-events-none bg-background opacity-50"
                  : "bg-card",
              )}
            >
              <div className="flex justify-between items-center">
                <label className="flex items-center gap-2 text-sm font-bold text-slate-800">
                  <Sliders size={16} /> Buffer Threshold
                </label>
                <span className="rounded bg-accent px-2 py-1 font-mono text-sm font-medium text-primary">
                  {bufferThreshold}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="20"
                {...register("bufferThreshold", { valueAsNumber: true })}
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-indigo-600"
                disabled={!useCalloutBuffer}
              />
              {errors.bufferThreshold && (
                <p className="text-xs text-red-500">{errors.bufferThreshold.message}</p>
              )}
              <p className="text-xs text-slate-500">
                Percentage of shift capacity to hold as reserve.
              </p>
            </div>
          </div>

          <h4 className="border-b border-slate-200/70 pb-2 pt-4 text-lg font-black text-slate-800">
            Compliance & Shift Rules
          </h4>
          <div className="grid md:grid-cols-2 gap-8">
            <div className="space-y-3 rounded-lg border border-border bg-card p-3">
              <label className="flex items-center gap-2 text-sm font-bold text-slate-800">
                <Clock size={16} /> Minimum Rest Period (Hours)
              </label>
              <input
                type="number"
                min="8"
                max="16"
                step="1"
                {...register("minRestPeriod", { valueAsNumber: true })}
                className="app-input w-full text-lg"
              />
              {errors.minRestPeriod && (
                <p className="text-xs text-red-500">{errors.minRestPeriod.message}</p>
              )}
              <p className="text-xs text-slate-500">
                Enforce minimum rest time between shifts (Current:{" "}
                {minRestPeriod} hrs).
              </p>
            </div>

            <div className="space-y-3 rounded-lg border border-border bg-card p-3">
              <label className="flex items-center gap-2 text-sm font-bold text-slate-800">
                <AlertTriangle size={16} /> Maximum Shift Length (Hours)
              </label>
              <input
                type="number"
                min="8"
                max="14"
                step="0.5"
                {...register("maxShiftLength", { valueAsNumber: true })}
                className="app-input w-full text-lg"
              />
              {errors.maxShiftLength && (
                <p className="text-xs text-red-500">{errors.maxShiftLength.message}</p>
              )}
              <p className="text-xs text-slate-500">
                Prevent burnout/fatigue by limiting shift duration (Current:{" "}
                {maxShiftLength} hrs).
              </p>
            </div>

            <div className="space-y-3 rounded-lg border border-border bg-card p-3 md:col-span-2">
              <label className="flex items-center gap-2 text-sm font-bold text-slate-800">
                <DollarSign size={16} /> Premium Shift Criteria
              </label>
              <div className="flex space-x-4">
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    {...register("premiumWeekend")}
                    className="rounded text-primary"
                  />
                  <label className="text-sm text-slate-700">
                    Weekend Shifts
                  </label>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    {...register("premiumHoliday")}
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
                    {...register("overtimeAvoidancePenalty", { valueAsNumber: true })}
                    className="app-input mt-1 w-full"
                  />
                  {errors.overtimeAvoidancePenalty && (
                    <p className="text-xs text-red-500">{errors.overtimeAvoidancePenalty.message}</p>
                  )}
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500">
                    Team Consistency
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="25"
                    {...register("teamConsistencyPenalty", { valueAsNumber: true })}
                    className="app-input mt-1 w-full"
                  />
                  {errors.teamConsistencyPenalty && (
                    <p className="text-xs text-red-500">{errors.teamConsistencyPenalty.message}</p>
                  )}
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500">
                    High-Risk Shift
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="50"
                    {...register("highRiskShiftPenalty", { valueAsNumber: true })}
                    className="app-input mt-1 w-full"
                  />
                  {errors.highRiskShiftPenalty && (
                    <p className="text-xs text-red-500">{errors.highRiskShiftPenalty.message}</p>
                  )}
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500">
                    Custom Preference
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="50"
                    {...register("customPreferencePenalty", { valueAsNumber: true })}
                    className="app-input mt-1 w-full"
                  />
                  {errors.customPreferencePenalty && (
                    <p className="text-xs text-red-500">{errors.customPreferencePenalty.message}</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="app-modal-footer">
          <button
            type="button"
            onClick={handleCancel}
            className="app-button-ghost"
          >
            Cancel
          </button>
          <button
            type="submit"
            data-testid="save-scheduling-config"
            disabled={!isDirty}
            className={cn(
              "app-button-primary",
              !isDirty && "opacity-50 cursor-not-allowed",
            )}
          >
            Save & Apply Settings
          </button>
        </div>
      </form>
    </ModalContainer>
  );
}
