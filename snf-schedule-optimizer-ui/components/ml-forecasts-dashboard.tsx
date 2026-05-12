import React, { useState } from "react";
import {
  Activity,
  ArrowRight,
  LucideIcon,
  ShieldAlert,
  TrendingUp,
  Users,
  X,
} from "lucide-react";

interface StatItem {
  label: string;
  value: string;
  alert?: boolean; // 'alert' is optional
}

interface ForecastDetails {
  chartLabel: string;
  stats: StatItem[];
  insight: string;
}

interface ForecastItem {
  id: string;
  title: string;
  subtitle: string;
  // For component props like icons, we use React.ElementType (or React.FC<any>)
  icon: LucideIcon;
  riskLevel: string;
  color: string;
  bg: string;
  border: string;
  summary: string;
  details: ForecastDetails;
}

// --- COMPONENT: MlForecastsDashboard ---
export default function MlForecastsDashboard() {
  const [activeInsight, setActiveInsight] = useState<ForecastItem | null>(null);

  const forecasts: ForecastItem[] = [
    {
      id: "hppd",
      title: "HPPD Forecasting",
      subtitle: "Next 30 Days",
      icon: Activity,
      riskLevel: "Medium",
      color: "text-[#168039]",
      bg: "bg-[#DFFFEA]",
      border: "border-[#28A745]",
      summary: "Predicted drop in HPPD on weekends starting Nov 20th.",
      details: {
        chartLabel: "Hours Per Patient Day (Trend)",
        stats: [
          { label: "Current Avg", value: "3.62" },
          { label: "Predicted Avg", value: "3.41", alert: true },
          { label: "Variance", value: "-0.21" },
        ],
        insight:
          "Machine learning models detect a recurring staffing gap on Saturday nights. Recommendation: Pre-book 2 PRN shifts for Nov 23 & 30.",
      },
    },
    {
      id: "turnover",
      title: "Turnover Risk",
      subtitle: "Staff Retention AI",
      icon: Users,
      riskLevel: "High",
      color: "text-[#FBC02D]",
      bg: "bg-[#FFF8E1]",
      border: "border-[#FBC02D]",
      summary: "3 High-Performance RNs flagged for burnout risk.",
      details: {
        chartLabel: "Burnout Risk Index",
        stats: [
          { label: "At-Risk Staff", value: "3" },
          { label: "Primary Factor", value: "Overtime" },
          { label: "Flight Risk", value: "78%", alert: true },
        ],
        insight:
          "Analysis of time-card data shows Nurse J. Doe and M. Smith have worked >60hrs for 4 consecutive weeks. Immediate schedule relief recommended.",
      },
    },
    {
      id: "safety",
      title: "Safety & Compliance",
      subtitle: "Incident Prediction",
      icon: ShieldAlert,
      riskLevel: "Low",
      color: "text-[#28A745]",
      bg: "bg-[#DFFFEA]",
      border: "border-[#28A745]",
      summary: "Labor law compliance is stable. Low injury risk.",
      details: {
        chartLabel: "Safety Incident Probability",
        stats: [
          { label: "Compliance Score", value: "98%" },
          { label: "Missed Breaks", value: "12" },
          { label: "Incident Prob.", value: "<1%" },
        ],
        insight:
          "No major red flags. Minor uptick in missed breaks in Wing C. Suggest auditing break-room logs.",
      },
    },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <div className="grid gap-3 lg:grid-cols-3">
        {/* Forecast Cards Column */}
        <div className="space-y-2 lg:col-span-1">
          {forecasts.map((item, idx) => (
            <button
              key={item.id}
              data-testid={`forecast-${item.id}`}
              onClick={() => setActiveInsight(item)}
              type="button"
              style={{ animationDelay: `${idx * 100}ms` }}
              className={`
                                  group relative cursor-pointer overflow-hidden rounded-lg border p-3 text-left transition-all duration-200 animate-in slide-in-from-left-4
                                ${
                                  activeInsight?.id === item.id
                                    ? `bg-white ${item.border} ring-1 ring-[#168039]/20 shadow-sm`
                                    : "border-[#E0E0E0] bg-white shadow-sm hover:border-[#28A745] hover:bg-[#DFFFEA]"
                                  }
                             `}
              aria-pressed={activeInsight?.id === item.id}
            >
              <div
                className={`absolute right-0 top-0 rounded-bl-2xl p-1 px-2 text-[10px] font-black uppercase ${item.bg} ${item.color}`}
              >
                {item.riskLevel} Risk
              </div>
              <div className="flex items-start space-x-4">
                <div className={`rounded-lg p-3 ${item.bg} ${item.color}`}>
                  <item.icon size={20} />
                </div>
                <div>
                  <h3 className="font-black text-slate-900">{item.title}</h3>
                  <p className="text-xs font-bold text-slate-500">
                    {item.subtitle}
                  </p>
                  <p className="mt-2 text-xs leading-snug text-slate-600">
                    {item.summary}
                  </p>
                </div>
              </div>
              {activeInsight?.id === item.id && (
                <div className="mt-3 flex justify-end">
                <ArrowRight size={16} className="text-[#168039]" />
                </div>
              )}
            </button>
          ))}
        </div>

        {/* Detail View Column */}
        <div className="lg:col-span-2">
          {activeInsight ? (
            <div
              key={activeInsight.id}
              className="app-card h-full overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-300"
            >
              <div
                className={`flex items-start justify-between border-b border-[#E0E0E0] p-4 ${activeInsight.bg}`}
              >
                <div>
                  <div className="flex items-center space-x-2 mb-1">
                    <activeInsight.icon
                      size={18}
                      className={activeInsight.color}
                    />
                    <span
                      className={`text-xs font-medium uppercase tracking-wide ${activeInsight.color}`}
                    >
                      Deep Dive Analysis
                    </span>
                  </div>
                  <h3 className="app-title text-2xl">
                    {activeInsight.title}
                  </h3>
                </div>
                <button
                  onClick={() => setActiveInsight(null)}
                  className="rounded-full p-1 text-slate-500 hover:bg-black/5"
                  aria-label="Close forecast details"
                >
                  <X size={20} />
                </button>
              </div>

              <div className="space-y-4 p-4 md:p-5">
                {/* Key Stats Row */}
                <div className="grid grid-cols-3 gap-2">
                  {activeInsight.details.stats.map((stat, idx) => (
                    <div
                      key={idx}
                      className="app-soft-panel p-3 text-center"
                    >
                      <p className="text-xs font-medium uppercase tracking-wide text-[#6C757D]">
                        {stat.label}
                      </p>
                      <p
                        className={`mt-1 text-xl font-semibold md:text-2xl ${stat.alert ? "text-red-600" : "text-[#212529]"}`}
                      >
                        {stat.value}
                      </p>
                    </div>
                  ))}
                </div>

                {/* Mock Chart Area */}
                <div className="space-y-2">
                  <h4 className="flex items-center gap-2 text-sm font-black text-slate-700">
                    <TrendingUp size={16} />
                    {activeInsight.details.chartLabel}
                  </h4>
                  <div className="flex h-48 items-end justify-between rounded-lg border border-dashed border-[#E0E0E0] bg-[#F4F6F8] p-4 px-8">
                    {[40, 65, 45, 80, 55, 90, 70].map((h, i) => (
                      <div
                        key={i}
                        className="group relative w-8 rounded-t-lg bg-[#DFFFEA] transition-colors hover:bg-[#28A745]"
                        style={{ height: `${h}%` }}
                      >
                         <div className="absolute -top-8 left-1/2 -translate-x-1/2 rounded-lg bg-[#212529] px-2 py-1 text-[10px] text-white opacity-0 transition group-hover:opacity-100">
                          Data Point
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* AI Insight Box */}
                <div className="flex items-start space-x-3 rounded-lg border border-[#28A745]/30 bg-[#DFFFEA] p-4">
                  <div className="mt-1 rounded-lg bg-white p-2 text-[#168039] shadow-none">
                    <activeInsight.icon size={16} />
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-[#168039]">
                      AI Recommendation
                    </h4>
                    <p className="mt-1 text-sm leading-relaxed text-[#212529]">
                      {activeInsight.details.insight}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="app-card flex h-full min-h-[360px] flex-col items-center justify-center border-dashed border-indigo-200/80 p-6 text-center animate-in fade-in duration-500">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-lg bg-white text-[#168039] shadow-sm">
                <Activity size={32} />
              </div>
              <h3 className="text-lg font-black text-slate-700">
                Select a Forecast Module
              </h3>
              <p className="mt-2 max-w-sm text-slate-500">
                Click on one of the prediction cards on the left to view
                detailed AI analysis and actionable insights.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
