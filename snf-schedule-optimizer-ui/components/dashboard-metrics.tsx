import React from "react";
import { type ModuleOption } from "@/components/dashboard-tabs";
import { metricToneVariants } from "@/components/ui/styles";
import { useExecutiveMetrics } from "@/hooks/use-executive-metrics";

interface DashboardMetricsProps {
  activeModule: ModuleOption;
}

export default function DashboardMetrics({ activeModule }: DashboardMetricsProps) {
  const { metrics } = useExecutiveMetrics(activeModule);

  return (
    <aside className="2xl:flex 2xl:min-h-0 2xl:self-stretch 2xl:items-center">
      <div
        key={activeModule}
        className="grid gap-2 md:grid-cols-2 2xl:w-full 2xl:max-w-xs 2xl:grid-cols-1 2xl:overflow-auto animate-in fade-in slide-in-from-bottom-4 duration-500"
      >
        {metrics.map((metric) => (
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
