import React from "react";
import {
  AlertTriangle,
  BarChart2,
  Brain,
  CheckCircle2,
  TrendingDown,
  Users,
} from "lucide-react";
import { type ModuleOption } from "@/components/dashboard-tabs";
import { metricToneVariants } from "@/components/ui/styles";

type MetricTone = "success" | "warning" | "neutral";

interface ExecutiveMetric {
  label: string;
  value: string;
  detail: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  tone: MetricTone;
}

export type { MetricTone, ExecutiveMetric };

interface DashboardMetricsProps {
  activeModule: ModuleOption;
  scheduleCount: number;
}

export default function DashboardMetrics({
  activeModule,
  scheduleCount,
}: DashboardMetricsProps) {
  const executiveMetrics: Record<ModuleOption, ExecutiveMetric[]> = {
    scheduling: [
      {
        label: "Coverage Score",
        value: scheduleCount > 0 ? "96%" : "--",
        detail: "Target-ready census coverage",
        icon: CheckCircle2,
        tone: "success",
      },
      {
        label: "Open Shifts",
        value: scheduleCount > 0 ? "7" : "--",
        detail: "Needs planner review",
        icon: AlertTriangle,
        tone: "warning",
      },
      {
        label: "Agency Hours",
        value: scheduleCount > 0 ? "-18%" : "--",
        detail: "Projected vs baseline",
        icon: TrendingDown,
        tone: "success",
      },
      {
        label: "Staff Mix",
        value: scheduleCount > 0 ? "82%" : "--",
        detail: "Internal team utilization",
        icon: Users,
        tone: "success",
      },
    ],
    analyzer: [
      {
        label: "Labor Spend",
        value: "$142.5k",
        detail: "Month-to-date cost baseline",
        icon: BarChart2,
        tone: "neutral",
      },
      {
        label: "Agency Utilization",
        value: "18.5%",
        detail: "Down 2.1% from last cycle",
        icon: Users,
        tone: "success",
      },
      {
        label: "Avg HPPD",
        value: "3.82",
        detail: "Tracking above 3.6 target",
        icon: CheckCircle2,
        tone: "success",
      },
      {
        label: "Overtime Risk",
        value: "8.4%",
        detail: "Needs reduction below 5%",
        icon: AlertTriangle,
        tone: "warning",
      },
    ],
    "ml-forecasts": [
      {
        label: "Weekend HPPD",
        value: "3.41",
        detail: "Forecasted dip late this month",
        icon: TrendingDown,
        tone: "warning",
      },
      {
        label: "Burnout Flags",
        value: "3 RNs",
        detail: "High-retention staff at risk",
        icon: Users,
        tone: "warning",
      },
      {
        label: "Compliance Score",
        value: "98%",
        detail: "Safety indicators remain stable",
        icon: CheckCircle2,
        tone: "success",
      },
      {
        label: "Action Queue",
        value: "2 PRN",
        detail: "Pre-book weekend coverage",
        icon: Brain,
        tone: "neutral",
      },
    ],
  };

  const activeExecutiveMetrics = executiveMetrics[activeModule];

  return (
    <aside className="2xl:flex 2xl:min-h-0 2xl:self-stretch 2xl:items-center">
      <div
        key={activeModule}
        className="grid gap-2 md:grid-cols-2 2xl:w-full 2xl:max-w-xs 2xl:grid-cols-1 2xl:overflow-auto animate-in fade-in slide-in-from-bottom-4 duration-500"
      >
        {activeExecutiveMetrics.map((metric) => (
          <div
            key={metric.label}
            className="app-card-interactive p-4"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  {metric.label}
                </p>
                <p className="app-title mt-2 text-3xl">{metric.value}</p>
              </div>
              <div className={metricToneVariants({ tone: metric.tone })}>
                <metric.icon size={19} />
              </div>
            </div>
            <p className="mt-2 text-sm font-normal text-muted-foreground">
              {metric.detail}
            </p>
          </div>
        ))}
      </div>
    </aside>
  );
}
