import React from "react";
import { TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  Calendar,
  FlaskConical,
  Brain,
  BarChart2,
} from "lucide-react";
import { segmentedButtonVariants } from "@/components/ui/styles";

export const moduleOptions = ["scheduling", "analyzer", "ml-forecasts"] as const;
export type ModuleOption = (typeof moduleOptions)[number];

interface DashboardTabsProps {
  selectedFacility: {
    facilityId: string;
    orgId: string;
  } | null;
  isLoading: boolean;
  scheduleCount: number;
  showPulse: boolean;
}

const renderTabTrigger = (
  value: ModuleOption,
  icon: React.ReactNode,
  label: string,
  showPulse: boolean,
  isPulse = false,
) => {
    return (
      <TabsTrigger
        data-testid={`tab-${value}`}
        value={value}
        className={cn(
        "h-auto min-w-fit justify-center gap-1.5 sm:text-sm",
        segmentedButtonVariants({ size: "md" }),
        "data-[state=active]:bg-card data-[state=active]:text-primary data-[state=active]:shadow-none",
        isPulse &&
          showPulse &&
          "animate-pulse bg-accent ring-2 ring-primary/20 hover:bg-accent",
      )}
    >
      {icon}
      <span>{label}</span>
    </TabsTrigger>
  );
};

export default function DashboardTabs({
  selectedFacility,
  isLoading,
  scheduleCount,
  showPulse,
}: DashboardTabsProps) {
  return (
    <div className="app-shell-card mb-6 overflow-hidden p-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] xl:items-center">
        <div className="min-w-0">
          <div className="app-eyebrow mb-2 flex items-center gap-2">
            <Calendar size={15} />
            Command Dashboard
          </div>
          <h1 className="app-title text-xl sm:text-2xl">
            Staffing Command Center
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <div
              data-testid="dashboard-demo-mode"
              className="flex items-center gap-1.5 font-medium text-primary"
            >
              <FlaskConical size={14} />
              <span>Demo mode</span>
            </div>
            <span className="hidden text-border sm:inline">/</span>
            <p className="min-w-0">
              Explore scheduling, scenarios, and forecasts
            </p>
          </div>
        </div>

        <div className="flex justify-center xl:justify-self-center">
          <div
            data-testid="facility-summary"
            className="app-soft-panel flex w-full max-w-md flex-col items-center gap-1 px-4 py-2 text-center text-xs text-muted-foreground sm:w-auto sm:min-w-[320px]"
          >
            <div>
              <span className="font-medium text-foreground">Facility:</span>{" "}
              {selectedFacility
                ? `${selectedFacility.facilityId} (${selectedFacility.orgId})`
                : isLoading
                  ? "Loading..."
                  : "None"}
            </div>
            <div>
              <span className="font-medium text-foreground">Loaded days:</span>{" "}
              {scheduleCount}
            </div>
          </div>
        </div>

        <div className="flex xl:justify-end">
          <TabsList className="app-segmented flex h-auto w-full flex-wrap justify-start gap-1 xl:w-fit" data-testid="module-menu">
            {renderTabTrigger("scheduling", <Calendar size={16} />, "Scheduling", showPulse)}
            {renderTabTrigger("analyzer", <BarChart2 size={16} />, "Scenario Analyzer", showPulse)}
            {renderTabTrigger("ml-forecasts", <Brain size={16} />, "ML Forecasts", showPulse, true)}
          </TabsList>
        </div>
      </div>
    </div>
  );
}
