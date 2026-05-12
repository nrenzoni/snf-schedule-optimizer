import React from "react";
import {
  CheckCircle,
  Clock,
  DollarSign,
  Heart,
  ListChecks,
  Scale,
  Smile,
  Users,
  X,
} from "lucide-react";
import ModalContainer from "../modal-container";

export interface SchedulerSettings {
  useMLForecast: boolean;
  useCalloutBuffer: boolean;
  bufferThreshold: number;
  minRestPeriod: number;
  maxShiftLength: number;
  premiumWeekend: boolean;
  premiumHoliday: boolean;
}

interface ScheduleSummaryModalProps {
  settings: SchedulerSettings; // The configuration used to generate the summary
  isOpen: boolean;
  onClose: () => void; // Function that takes no arguments and returns nothing
}

// --- COMPONENT: ScheduleSummaryModal ---
export function ScheduleSummaryModal({
  settings,
  isOpen,
  onClose,
}: ScheduleSummaryModalProps) {
  // Mock data generation (kept here for context)
  const rawMetrics = {
    preferenceMatch: 94,
    overtimePercentage: 6.2,
  };

  // Mock data generation based on settings for demonstration
  const metrics = {
    // Operational Metrics
    avgCoverage: "98.5%",
    shiftsBelowThreshold: settings.useCalloutBuffer ? 2 : 7,
    restPeriodViolations: settings.minRestPeriod > 10 ? 0 : 3,
    maxShiftViolations: settings.maxShiftLength < 12 ? 1 : 0,

    // Financial Metrics
    totalLaborCost: "$1,254,000",
    totalPremiumPay:
      settings.premiumWeekend || settings.premiumHoliday ? "$45,200" : "$2,100",
    costPerPatientDay: "$85.45",
    overtimePercentage: `${rawMetrics.overtimePercentage.toFixed(1)}%`, // Format back to string
    overtimeNumerical: rawMetrics.overtimePercentage, // Keep numerical for logic

    // Wellbeing Metrics (NEW)
    preferenceMatch: `${rawMetrics.preferenceMatch}%`, // Format back to string
    preferenceMatchNumerical: rawMetrics.preferenceMatch, // Keep numerical for logic
    teamSynergy: "87%",
    weekendFairness: "Balanced", // or 'Skewed'
    avgConsecutiveDays: "3.4",
  };

  return (
    // 1. Replaced the entire backdrop div with ModalContainer
    <ModalContainer
      isOpen={isOpen}
      onClose={onClose}
      contentClassName="max-w-6xl"
    >
      {/* 2. Content starts directly with the outermost content div,
               which no longer needs transition classes. */}
      <div className="w-full overflow-hidden bg-white/82">
        {/* HEADER */}
        <div className="flex items-center justify-between border-b border-[#E0E0E0] bg-white p-4 text-[#212529]">
          <div className="flex items-center space-x-2">
            <ListChecks size={24} />
            <h3 className="text-xl font-black">Monthly Schedule Summary</h3>
          </div>
          {/* Close Button relies on onClose prop */}
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-[#6C757D] hover:bg-[#E9EEF1] hover:text-[#212529]"
          >
            <X size={20} />
          </button>
        </div>

        {/* Changed to 3 columns grid */}
        <div className="p-6 grid lg:grid-cols-3 gap-8 max-h-[80vh] overflow-y-auto">
          {/* COLUMN 1: Operational Metrics */}
          <div>
            <h4 className="mb-4 flex items-center gap-2 border-b border-[#E0E0E0] pb-2 text-lg font-semibold text-[#168039]">
              <CheckCircle size={18} /> Operational Compliance
            </h4>
            <div className="space-y-3">
              <div className="flex justify-between rounded-lg border border-[#28A745]/30 bg-[#DFFFEA] p-3">
                <span className="text-gray-700 font-medium">
                  Avg. Daily Coverage
                </span>
                <span className="text-xl font-semibold text-[#168039]">
                  {metrics.avgCoverage}
                </span>
              </div>

              <div
                className={`flex justify-between rounded-lg border p-3 ${metrics.shiftsBelowThreshold > 5 ? "border-red-200 bg-red-50" : "border-[#28A745]/30 bg-[#DFFFEA]"}`}
              >
                <div>
                  <span className="text-gray-700 font-medium">
                    Risk Shifts (Low Buffer)
                  </span>
                </div>
                <span
                  className={`text-xl font-black ${metrics.shiftsBelowThreshold > 5 ? "text-rose-600" : "text-emerald-600"}`}
                >
                  {metrics.shiftsBelowThreshold}
                </span>
              </div>

              <div
                className={`flex justify-between rounded-lg border p-3 ${metrics.restPeriodViolations > 0 ? "border-[#FBC02D]/40 bg-[#FFF8E1]" : "border-[#E0E0E0] bg-white"}`}
              >
                <div>
                  <span className="text-gray-700 font-medium">
                    Rest Period Violations
                  </span>
                </div>
                <span
                  className={`text-xl font-black ${metrics.restPeriodViolations > 0 ? "text-amber-600" : "text-slate-700"}`}
                >
                  {metrics.restPeriodViolations}
                </span>
              </div>

              <div
                className={`flex justify-between rounded-lg border p-3 ${metrics.maxShiftViolations > 0 ? "border-[#FBC02D]/40 bg-[#FFF8E1]" : "border-[#E0E0E0] bg-white"}`}
              >
                <div>
                  <span className="text-gray-700 font-medium">
                    Max Shift Violations
                  </span>
                </div>
                <span
                  className={`text-xl font-black ${metrics.maxShiftViolations > 0 ? "text-amber-600" : "text-slate-700"}`}
                >
                  {metrics.maxShiftViolations}
                </span>
              </div>
            </div>
          </div>

          {/* COLUMN 2: Financial Metrics */}
          <div>
            <h4 className="mb-4 flex items-center gap-2 border-b border-[#E0E0E0] pb-2 text-lg font-semibold text-[#168039]">
              <DollarSign size={18} /> Financial Impact
            </h4>
            <div className="space-y-3">
              <div className="flex justify-between rounded-lg border border-[#28A745]/30 bg-[#DFFFEA] p-3">
                <span className="text-gray-700 font-medium">
                  Est. Labor Cost
                </span>
                <span className="text-xl font-semibold text-[#168039]">
                  {metrics.totalLaborCost}
                </span>
              </div>

              <div className="flex justify-between rounded-lg border border-[#E0E0E0] bg-white p-3">
                <span className="text-gray-700 font-medium">
                  Cost Per Patient Day
                </span>
                <span className="font-bold text-xl text-gray-800">
                  {metrics.costPerPatientDay}
                </span>
              </div>

              <div className="flex justify-between rounded-lg border border-[#E0E0E0] bg-white p-3">
                <span className="text-gray-700 font-medium">Overtime %</span>
                <span
                  className={`text-xl font-black ${metrics.overtimeNumerical > 5.0 ? "text-rose-600" : "text-emerald-600"}`}
                >
                  {metrics.overtimePercentage}
                </span>
              </div>

              <div className="flex justify-between rounded-lg border border-[#E0E0E0] bg-white p-3">
                <div>
                  <span className="text-gray-700 font-medium">Premium Pay</span>
                </div>
                <span className="font-bold text-xl text-gray-800">
                  {metrics.totalPremiumPay}
                </span>
              </div>
            </div>
          </div>

          {/* COLUMN 3: Wellbeing Metrics */}
          <div>
            <h4 className="mb-4 flex items-center gap-2 border-b border-[#E0E0E0] pb-2 text-lg font-semibold text-[#168039]">
              <Heart size={18} className="text-pink-600" />
              Staff Wellbeing
            </h4>
            <div className="space-y-3">
              {/* Preference Match */}
              <div className="rounded-lg border border-[#28A745]/30 bg-[#DFFFEA] p-3">
                <div className="flex justify-between mb-1">
                  <span className="text-gray-700 font-medium flex items-center gap-2">
                    <Smile size={16} className="text-[#168039]" /> Preferences
                    Met
                  </span>
                  <span className="text-xl font-semibold text-[#168039]">
                    {metrics.preferenceMatch}
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-[#E9EEF1]">
                  <div
                    className="h-2 rounded-full bg-[#28A745]"
                    style={{ width: `${metrics.preferenceMatchNumerical}%` }}
                  ></div>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Ratio of shift/off requests granted.
                </p>
              </div>

              {/* Team Synergy */}
              <div className="flex justify-between rounded-lg border border-[#E0E0E0] bg-white p-3">
                <div>
                  <span className="text-gray-700 font-medium flex items-center gap-2">
                    <Users size={16} /> Team Synergy
                  </span>
                  <p className="text-xs text-gray-400">
                    Preferred pairings met
                  </p>
                </div>
                <span className="font-bold text-xl text-gray-800">
                  {metrics.teamSynergy}
                </span>
              </div>

              {/* Fairness Score */}
              <div className="flex justify-between rounded-lg border border-[#E0E0E0] bg-white p-3">
                <div>
                  <span className="text-gray-700 font-medium flex items-center gap-2">
                    <Scale size={16} /> Fairness Index
                  </span>
                  <p className="text-xs text-gray-400">
                    Weekend/Holiday equity
                  </p>
                </div>
                <span className="rounded-lg bg-[#DFFFEA] px-2 py-0.5 text-lg font-semibold text-[#28A745]">
                  {metrics.weekendFairness}
                </span>
              </div>

              {/* Fatigue Watch */}
              <div className="flex justify-between rounded-lg border border-[#E0E0E0] bg-white p-3">
                <div>
                  <span className="text-gray-700 font-medium flex items-center gap-2">
                    <Clock size={16} /> Fatigue Watch
                  </span>
                  <p className="text-xs text-gray-400">Avg consecutive days</p>
                </div>
                <span className="font-bold text-xl text-gray-800">
                  {metrics.avgConsecutiveDays}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-slate-200/70 bg-slate-50/85 p-4">
          <p className="text-sm text-gray-500 italic pl-2">
            * Recommendation: High synergy score suggests strong team morale for
            this period.
          </p>
          <button
            onClick={onClose}
            className="app-button-primary px-6"
          >
            Close Summary
          </button>
        </div>
      </div>
    </ModalContainer>
  );
}
