import React, { useState } from "react";
import {
  Activity,
  ArrowRight,
  Brain,
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
      color: "text-blue-600",
      bg: "bg-blue-50",
      border: "border-blue-200",
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
      color: "text-orange-600",
      bg: "bg-orange-50",
      border: "border-orange-200",
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
      color: "text-green-600",
      bg: "bg-green-50",
      border: "border-green-200",
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
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8 flex items-center space-x-3">
        <div className="p-3 bg-purple-100 rounded-lg text-purple-700">
          <Brain size={24} />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-gray-800">ML Forecasts</h2>
          <p className="text-gray-500">
            AI-driven predictions for proactive management
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Forecast Cards Column */}
        <div className="space-y-4 lg:col-span-1">
          {forecasts.map((item, idx) => (
            <div
              key={item.id}
              onClick={() => setActiveInsight(item)}
              style={{ animationDelay: `${idx * 100}ms` }}
              className={`
                                cursor-pointer p-4 rounded-xl border-2 transition-all duration-200 relative overflow-hidden group animate-in slide-in-from-left-4
                                ${
                                  activeInsight?.id === item.id
                                    ? `bg-white ${item.border} ring-1 ring-offset-2 ring-indigo-500 shadow-md`
                                    : "bg-white border-transparent hover:border-gray-200 hover:shadow-sm"
                                }
                            `}
            >
              <div
                className={`absolute top-0 right-0 p-1 px-2 text-[10px] font-bold uppercase rounded-bl-lg ${item.bg} ${item.color}`}
              >
                {item.riskLevel} Risk
              </div>
              <div className="flex items-start space-x-4">
                <div className={`p-3 rounded-lg ${item.bg} ${item.color}`}>
                  <item.icon size={20} />
                </div>
                <div>
                  <h3 className="font-bold text-gray-800">{item.title}</h3>
                  <p className="text-xs text-gray-500 font-medium">
                    {item.subtitle}
                  </p>
                  <p className="text-xs text-gray-600 mt-2 leading-snug">
                    {item.summary}
                  </p>
                </div>
              </div>
              {activeInsight?.id === item.id && (
                <div className="mt-3 flex justify-end">
                  <ArrowRight size={16} className="text-indigo-500" />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Detail View Column */}
        <div className="lg:col-span-2">
          {activeInsight ? (
            <div
              key={activeInsight.id}
              className="bg-white rounded-xl shadow-lg border border-gray-100 h-full overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-300"
            >
              <div
                className={`p-6 border-b ${activeInsight.bg} flex justify-between items-start`}
              >
                <div>
                  <div className="flex items-center space-x-2 mb-1">
                    <activeInsight.icon
                      size={18}
                      className={activeInsight.color}
                    />
                    <span
                      className={`text-xs font-bold uppercase tracking-wider ${activeInsight.color}`}
                    >
                      Deep Dive Analysis
                    </span>
                  </div>
                  <h3 className="text-2xl font-bold text-gray-900">
                    {activeInsight.title}
                  </h3>
                </div>
                <button
                  onClick={() => setActiveInsight(null)}
                  className="p-1 hover:bg-black/5 rounded-full text-gray-500"
                >
                  <X size={20} />
                </button>
              </div>

              <div className="p-6 md:p-8 space-y-8">
                {/* Key Stats Row */}
                <div className="grid grid-cols-3 gap-4">
                  {activeInsight.details.stats.map((stat, idx) => (
                    <div
                      key={idx}
                      className="bg-gray-50 p-4 rounded-xl border border-gray-100 text-center"
                    >
                      <p className="text-xs text-gray-500 uppercase font-semibold">
                        {stat.label}
                      </p>
                      <p
                        className={`text-xl md:text-2xl font-bold mt-1 ${stat.alert ? "text-red-600" : "text-gray-800"}`}
                      >
                        {stat.value}
                      </p>
                    </div>
                  ))}
                </div>

                {/* Mock Chart Area */}
                <div className="space-y-2">
                  <h4 className="text-sm font-bold text-gray-700 flex items-center gap-2">
                    <TrendingUp size={16} />
                    {activeInsight.details.chartLabel}
                  </h4>
                  <div className="h-48 bg-gray-50 rounded-xl border border-dashed border-gray-300 flex items-end justify-between p-4 px-8">
                    {[40, 65, 45, 80, 55, 90, 70].map((h, i) => (
                      <div
                        key={i}
                        className="w-8 bg-indigo-200 rounded-t-md hover:bg-indigo-400 transition-colors relative group"
                        style={{ height: `${h}%` }}
                      >
                        <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-[10px] py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition">
                          Data Point
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* AI Insight Box */}
                <div className="bg-indigo-50 border border-indigo-100 p-4 rounded-xl flex items-start space-x-3">
                  <div className="bg-white p-2 rounded-full shadow-sm text-indigo-600 mt-1">
                    <Brain size={16} />
                  </div>
                  <div>
                    <h4 className="font-bold text-indigo-900 text-sm">
                      AI Recommendation
                    </h4>
                    <p className="text-sm text-indigo-800 mt-1 leading-relaxed">
                      {activeInsight.details.insight}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full min-h-[400px] flex flex-col items-center justify-center text-center p-8 bg-gray-50 rounded-xl border-2 border-dashed border-gray-200 animate-in fade-in duration-500">
              <div className="w-16 h-16 bg-white rounded-full shadow-sm flex items-center justify-center mb-4 text-purple-300">
                <Brain size={32} />
              </div>
              <h3 className="text-lg font-bold text-gray-700">
                Select a Forecast Module
              </h3>
              <p className="text-gray-400 max-w-sm mt-2">
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
