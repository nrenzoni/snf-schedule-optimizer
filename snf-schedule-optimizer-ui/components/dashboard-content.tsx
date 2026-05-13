"use client";

import { useUIStore } from "@/store/uiStore";
import { useShallow } from "zustand/react/shallow";
import React, { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertTriangle,
  BarChart2,
  Brain,
  Calendar,
  CheckCircle2,
  GanttChartSquare,
  LayoutList,
  ListChecks,
  Settings,
  TrendingDown,
  Users,
  Zap,
} from "lucide-react";
import ScheduleListView from "@/components/schedule-list-view";
import { Toaster } from "@/components/ui/sonner";
import ScenarioAnalyzerDashboard from "@/components/scenario-analyzer-dashboard";
import ShiftModal from "@/components/modals/shift-modal";
import { SchedulingConfigModal } from "@/components/modals/scheduling-config-modal";
import {
  SchedulerSettings,
  ScheduleSummaryModal,
} from "@/components/modals/schedule-summary-modal";
import MlForecastsDashboard from "@/components/ml-forecasts-dashboard";
import useScheduleQuery from "@/hooks/use-schedule-query";
import { parseAsString, parseAsStringLiteral, useQueryState } from "nuqs";
import { TODAY_STRING } from "@/utils/scheduling-logic";
import { useScheduling } from "@/hooks/use-scheduling";
import NurseDetailsPanel from "@/components/nurse-details-panel";
import DemoModeBanner from "@/components/demo-mode-banner";
import DashboardEmptyState from "@/components/dashboard-empty-state";
import { useSchedulingStore } from "@/store/schedulingStore";
import { ScheduleQueryError } from "@/hooks/use-schedule-query";
import { isUsingFallbackApiBaseUrl } from "@/api/scheduling-client";
import {
  metricToneVariants,
  segmentedButtonVariants,
} from "@/components/ui/styles";

interface DashboardShellProps {
  timelineView: React.ReactNode;
}

const viewOptions = ["list", "timeline"] as const;
const moduleOptions = ["scheduling", "analyzer", "ml-forecasts"] as const;

// 1. CREATE AN INNER COMPONENT
// This component will be a child of QueryClientProvider, so hooks will work here.
export default function DashboardContent({
  timelineView,
}: DashboardShellProps) {
  // --- A. URL STATE (Nuqs) ---
  const [anchorDateStr] = useQueryState(
    "anchor",
    parseAsString.withDefault(TODAY_STRING),
  );

  // --- B. DERIVED STATE ---
  const currentViewAnchorDate = useMemo(
    () => new Date(anchorDateStr),
    [anchorDateStr],
  );

  const [activeModule, setActiveModule] = useQueryState(
    "tab",
    parseAsStringLiteral(moduleOptions).withDefault("scheduling"),
  );

  // URL: /schedule?view=timeline
  const [viewMode, setViewMode] = useQueryState(
    "view",
    parseAsStringLiteral(viewOptions).withDefault("timeline"),
  );

  const uiStore = useUIStore(
    useShallow((state) => ({
      isConfigModalOpen: state.isConfigModalOpen,
      closeConfigModal: state.closeConfigModal,
      openConfigModal: state.openConfigModal,
      isSummaryModalOpen: state.isSummaryModalOpen,
      closeSummaryModal: state.closeSummaryModal,
      openSummaryModal: state.openSummaryModal,
    })),
  );

  const { selectedFacility, scheduleCount, isOptimizing } = useSchedulingStore(
    useShallow((state) => ({
      selectedFacility: state.selectedFacility,
      scheduleCount: state.scheduleMap.size,
      isOptimizing: state.isOptimizing,
    })),
  );

  // Call the hook. It handles URL parsing and derived state.
  const {
    // Modal State (Derived from URL)
    selectedDay,
    selectedShift,
    selectedNurse,
    isModalVisible,

    // Actions
    closeModal,
    selectShift,
    openNurseDetails,
    closeNurseDetails,
    removeNurseFromShift,
    addNurseToShift,

    // Calendar/Data State
    triggerOptimization,
  } = useScheduling();

  // THIS HOOK NOW WORKS because it is inside QueryClientProvider
  const { error, isLoading, refetch } = useScheduleQuery(currentViewAnchorDate);

  const [showPulse, setShowPulse] = useState(true);

  const [schedulerSettings, setSchedulerSettings] = useState<SchedulerSettings>(
    {
      useMLForecast: false,
      useCalloutBuffer: true,
      bufferThreshold: 10,
      minRestPeriod: 10,
      maxShiftLength: 12,
      premiumWeekend: true,
      premiumHoliday: false,
    },
  );

  function updateSchedulerSettings(
    key: keyof SchedulerSettings,
    value: SchedulerSettings[keyof SchedulerSettings],
  ) {
    setSchedulerSettings((prev) => ({ ...prev, [key]: value }));
  }

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowPulse(false);
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  const executiveMetrics = [
    {
      label: "Coverage Score",
      value: scheduleCount > 0 ? "96%" : "--",
      detail: "Target-ready census coverage",
      icon: CheckCircle2,
      tone: "success" as const,
    },
    {
      label: "Open Shifts",
      value: scheduleCount > 0 ? "7" : "--",
      detail: "Needs planner review",
      icon: AlertTriangle,
      tone: "warning" as const,
    },
    {
      label: "Agency Hours",
      value: scheduleCount > 0 ? "-18%" : "--",
      detail: "Projected vs baseline",
      icon: TrendingDown,
      tone: "success" as const,
    },
    {
      label: "Staff Mix",
      value: scheduleCount > 0 ? "82%" : "--",
      detail: "Internal team utilization",
      icon: Users,
      tone: "success" as const,
    },
  ];

  const renderTabTrigger = (
    value: (typeof moduleOptions)[number],
    icon: React.ReactNode,
    label: string,
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

  return (
    <div className="app-bg min-h-screen p-2 font-sans md:p-3">
      <div
        className={cn(
          "mx-auto transition-all duration-300 ease-in-out",
          activeModule === "scheduling" ? "max-w-[1800px]" : "max-w-4xl",
        )}
      >
        <DemoModeBanner />

        {isUsingFallbackApiBaseUrl ? (
          <div className="app-callout-warning mb-6 px-4 py-3 text-sm">
            <span className="font-semibold">API base URL fallback in use.</span>{" "}
            Set <code>NEXT_PUBLIC_API_BASE_URL</code> to point the demo at the
            intended backend instead of the default local address.
          </div>
        ) : null}

        <Tabs
          value={activeModule}
          onValueChange={(value) => void setActiveModule(value as typeof moduleOptions[number])}
          className="w-full"
        >
          <div className="app-shell-card mb-6 overflow-hidden p-4">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex min-w-0 items-center gap-3">
                <div className="app-eyebrow flex items-center gap-2">
                  <Calendar size={15} />
                  Staffing Command Center
                </div>
                <div className="hidden h-5 w-px bg-border sm:block" />
                <h1 className="app-title truncate text-sm sm:text-base">
                  Explore scheduling, scenarios, and forecasts
                </h1>
              </div>

              <div className="flex flex-col gap-2 lg:items-end">
                <TabsList className="app-segmented flex h-auto w-full flex-wrap justify-start gap-1 lg:w-fit" data-testid="module-menu">
                  {renderTabTrigger("scheduling", <Calendar size={16} />, "Scheduling")}
                  {renderTabTrigger("analyzer", <BarChart2 size={16} />, "Scenario Analyzer")}
                  {renderTabTrigger("ml-forecasts", <Brain size={16} />, "ML Forecasts", true)}
                </TabsList>

                <div className="app-soft-panel flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5 text-xs text-muted-foreground">
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
            </div>
          </div>

          {/*Tabs Content*/}
          <div className="min-h-[600px]">
            {error && (
              <DashboardEmptyState
                title={
                  error instanceof ScheduleQueryError &&
                  error.code === "NO_FACILITIES"
                    ? "No facilities available"
                    : "Schedule data could not be loaded"
                }
                description={error.message}
                actionLabel="Retry schedule fetch"
                onAction={() => {
                  void refetch();
                }}
              />
            )}

            <TabsContent value="scheduling" className="mt-0">
              <div className="space-y-2">
                {!error && !isLoading && scheduleCount === 0 ? (
                  <DashboardEmptyState
                    title="No schedule data returned"
                    description="The API responded successfully but did not return any days for the selected month. Try another month or retry the query."
                    actionLabel="Reload month"
                    onAction={() => {
                      void refetch();
                    }}
                    />
                ) : null}

                <div className="flex justify-end">
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <button
                      data-testid="optimize-schedule"
                      onClick={triggerOptimization}
                      disabled={isOptimizing}
                      className="app-button-primary min-h-9 whitespace-nowrap px-4 py-2"
                    >
                      <Zap size={16} />
                      <span>{isOptimizing ? "Optimizing..." : "Optimize"}</span>
                    </button>
                    <button
                      data-testid="open-schedule-summary"
                      onClick={uiStore.openSummaryModal}
                      className="app-button-secondary min-h-9 whitespace-nowrap px-4 py-2"
                    >
                      <ListChecks size={16} />
                      Summary
                    </button>
                    <button
                      data-testid="open-scheduling-config"
                      onClick={uiStore.openConfigModal}
                      className="app-button-secondary min-h-9 whitespace-nowrap px-4 py-2"
                    >
                      <Settings size={16} />
                      Configure
                    </button>
                    <div className="app-segmented flex space-x-1">
                      <button
                        data-testid="view-list"
                        onClick={() => setViewMode("list")}
                      className={segmentedButtonVariants({
                        size: "md",
                        active: viewMode === "list",
                      })}
                    >
                      <LayoutList size={14} /> <span>List</span>
                    </button>
                    <button
                      data-testid="view-timeline"
                      onClick={() => setViewMode("timeline")}
                      className={segmentedButtonVariants({
                        size: "md",
                        active: viewMode === "timeline",
                      })}
                    >
                        <GanttChartSquare size={14} /> <span>Timeline</span>
                      </button>
                    </div>
                  </div>
                </div>

                {viewMode === "list" ? (
                  <ScheduleListView />
                ) : (
                    <div className="app-card h-[calc(100vh-170px)] min-h-[560px] p-2">
                      {timelineView}
                    </div>
                )}

                <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                  {executiveMetrics.map((metric) => (
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
              </div>
            </TabsContent>

            <TabsContent
              value="analyzer"
              className="mt-0 animate-in fade-in slide-in-from-bottom-4 duration-500"
            >
              <ScenarioAnalyzerDashboard />
            </TabsContent>

            <TabsContent
              value="ml-forecasts"
              className="mt-0 animate-in fade-in slide-in-from-bottom-4 duration-500"
            >
              <MlForecastsDashboard />
            </TabsContent>
          </div>
        </Tabs>

        {/* Modals */}
        <ShiftModal
          selectedDay={selectedDay}
          selectedShift={selectedShift}
          selectedNurse={selectedNurse}
          isModalVisible={isModalVisible}
          closeModal={closeModal}
          selectShift={selectShift}
          openNurseDetails={openNurseDetails}
          // closeNurseDetails={closeNurseDetails}
          // removeNurseFromShift={removeNurseFromShift}
          // addNurseToShift={addNurseToShift}
          // closeNurseDetails={closeNurseDetails}
        >
          {/* 2. INJECT THE PANEL HERE via Composition */}
          {/* Only render if we have a selected nurse (or handle nulls inside the panel) */}
          {selectedNurse && (
            <NurseDetailsPanel
              selectedNurse={selectedNurse}
              closeNurseDetails={closeNurseDetails}
              removeNurseFromShift={removeNurseFromShift}
              addNurseToShift={addNurseToShift}
            />
          )}
        </ShiftModal>

        <SchedulingConfigModal
          settings={schedulerSettings}
          isOpen={uiStore.isConfigModalOpen}
          onClose={uiStore.closeConfigModal}
          onUpdate={updateSchedulerSettings}
        />

        <ScheduleSummaryModal
          settings={schedulerSettings}
          isOpen={uiStore.isSummaryModalOpen}
          onClose={uiStore.closeSummaryModal}
        />

        <Toaster position="bottom-center" richColors />
      </div>
    </div>
  );
}
