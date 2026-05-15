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
  FlaskConical,
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
import ErrorBoundary from "@/components/error-boundary";
import ScenarioAnalyzerDashboard from "@/components/scenario-analyzer-dashboard";
import ShiftModal from "@/components/modals/shift-modal";
import { SchedulingConfigModal } from "@/components/modals/scheduling-config-modal";
import { ScheduleSummaryModal } from "@/components/modals/schedule-summary-modal";
import MlForecastsDashboard from "@/components/ml-forecasts-dashboard";
import useScheduleQuery from "@/hooks/use-schedule-query";
import { parseAsString, parseAsStringLiteral, useQueryState } from "nuqs";
import { getTodayString } from "@/lib/scheduling-logic";
import { useScheduling } from "@/hooks/use-scheduling";
import { useOptimizationRunSync } from "@/hooks/use-optimization-run-sync";
import NurseDetailsPanel from "@/components/nurse-details-panel";
import DashboardEmptyState from "@/components/dashboard-empty-state";
import { useSchedulingStore } from "@/store/schedulingStore";
import { ScheduleQueryError } from "@/hooks/use-schedule-query";
import {
  metricToneVariants,
  segmentedButtonVariants,
} from "@/components/ui/styles";

type MetricTone = "success" | "warning" | "neutral";

interface ExecutiveMetric {
  label: string;
  value: string;
  detail: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  tone: MetricTone;
}

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
    parseAsString.withDefault(getTodayString()),
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

  const {
    selectedFacility,
    scheduleCount,
    activeRun,
    hydratePersistedDraftState,
    hasNewerVersion,
    latestKnownScheduleVersion,
    draftPatchCount,
    draftConflicts,
    schedulerSettings,
    latestOptimization,
    optimizationStats,
    optimizationFinancials,
  } = useSchedulingStore(
    useShallow((state) => ({
      selectedFacility: state.selectedFacility,
      scheduleCount: state.effectiveScheduleMap.size,
      activeRun: state.activeRun,
      hydratePersistedDraftState: state.hydratePersistedDraftState,
      hasNewerVersion: state.hasNewerVersion,
      latestKnownScheduleVersion: state.latestKnownScheduleVersion,
      draftPatchCount: state.draftState.patches.length,
      draftConflicts: state.draftState.conflicts,
      schedulerSettings: state.schedulerSettings,
      latestOptimization: state.latestOptimization,
      optimizationStats: state.optimizationStats,
      optimizationFinancials: state.optimizationFinancials,
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
    clearDraft,
    isRunActive,
    updateSchedulerSettings,
  } = useScheduling();

  // THIS HOOK NOW WORKS because it is inside QueryClientProvider
  const { error, isLoading, refetch } = useScheduleQuery(currentViewAnchorDate);

  const [showPulse, setShowPulse] = useState(true);

  const optimizeButtonFillWidth = activeRun ? `${Math.max(0, Math.min(100, activeRun.progressPercent))}%` : "0%";

  useOptimizationRunSync();

  useEffect(() => {
    hydratePersistedDraftState();
  }, [hydratePersistedDraftState]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowPulse(false);
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  const executiveMetrics: Record<(typeof moduleOptions)[number], ExecutiveMetric[]> = {
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
    <div className="app-bg min-h-screen p-2 font-sans md:p-3 xl:h-screen xl:overflow-hidden">
      <div className="mx-auto max-w-[1800px] xl:flex xl:h-full xl:flex-col">
        <Tabs
          value={activeModule}
          onValueChange={(value) => void setActiveModule(value as typeof moduleOptions[number])}
          className="w-full xl:min-h-0 xl:flex-1 xl:overflow-hidden"
        >
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
                  {renderTabTrigger("scheduling", <Calendar size={16} />, "Scheduling")}
                  {renderTabTrigger("analyzer", <BarChart2 size={16} />, "Scenario Analyzer")}
                  {renderTabTrigger("ml-forecasts", <Brain size={16} />, "ML Forecasts", true)}
                </TabsList>
              </div>
            </div>
          </div>

          {/*Tabs Content*/}
          <div className="min-h-[600px] xl:min-h-0 xl:flex-1 xl:overflow-hidden xl:pb-4">
            {error && (
              <DashboardEmptyState
                title={
                  error instanceof ScheduleQueryError &&
                  error.code === "NO_FACILITIES"
                    ? "No facilities available"
                    : error instanceof ScheduleQueryError &&
                        error.code === "MISSING_API_BASE_URL"
                      ? "Backend base URL is not configured"
                    : "Schedule data could not be loaded"
                }
                description={error.message}
                actionLabel="Retry schedule fetch"
                onAction={() => {
                  void refetch();
                }}
              />
            )}

            {!error ? (
              <div className="grid items-start gap-3 xl:h-full xl:min-h-0 xl:items-stretch 2xl:grid-cols-[minmax(0,1fr)_320px]">
                <div className="min-w-0 xl:flex xl:min-h-0 xl:flex-col">
                  <ErrorBoundary fallbackTitle="Schedule content error">
                  <TabsContent
                    value="scheduling"
                    className="mt-0 xl:flex xl:min-h-0 xl:flex-1 xl:flex-col xl:overflow-hidden"
                  >
                    <div className="space-y-2 xl:flex xl:min-h-0 xl:flex-1 xl:flex-col xl:gap-2 xl:space-y-0">
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
                          {hasNewerVersion ? (
                            <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                              Newer schedule version detected on the backend.
                              {latestKnownScheduleVersion > 0
                                ? ` Latest version: ${latestKnownScheduleVersion}.`
                                : null}
                            </div>
                          ) : null}
                          {draftPatchCount > 0 ? (
                            <button
                              data-testid="revert-staged-changes"
                              onClick={clearDraft}
                              className="app-button-secondary min-h-9 whitespace-nowrap px-4 py-2"
                            >
                              Revert {draftPatchCount} staged
                            </button>
                          ) : null}
                          <button
                            data-testid="optimize-schedule"
                            onClick={() => {
                              void triggerOptimization();
                            }}
                            disabled={isRunActive}
                            className="app-button-primary relative min-h-9 overflow-hidden whitespace-nowrap px-4 py-2"
                          >
                            {activeRun ? (
                              <span
                                aria-hidden="true"
                                className="absolute inset-y-0 left-0 bg-gradient-to-r from-primary/40 via-primary/70 to-emerald-400/80 transition-[width] duration-300"
                                style={{ width: optimizeButtonFillWidth }}
                              />
                            ) : null}
                            <span className="relative z-10 flex items-center gap-2">
                            <Zap size={16} />
                            <span>{isRunActive ? "Optimizing..." : "Optimize"}</span>
                            {activeRun ? <span className="text-xs">{activeRun.progressPercent}%</span> : null}
                            </span>
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
                        <div className="xl:min-h-0 xl:flex-1 xl:overflow-auto xl:pb-4">
                          <ScheduleListView />
                        </div>
                      ) : (
                        <div className="app-card min-h-[560px] p-2 xl:min-h-0 xl:flex-1 xl:overflow-hidden">
                          <div className="xl:flex xl:h-full xl:min-h-0 xl:flex-col">{timelineView}</div>
                        </div>
                      )}

                      {activeRun ? (
                        <div className="app-soft-panel flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm text-muted-foreground">
                          <div>
                            <span className="font-medium text-foreground">Run:</span> {activeRun.stage}
                            {activeRun.statusMessage ? ` - ${activeRun.statusMessage}` : null}
                          </div>
                          <div>
                            <span className="font-medium text-foreground">Progress:</span> {activeRun.progressPercent}%
                          </div>
                        </div>
                      ) : null}

                      {draftConflicts.length > 0 ? (
                        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                          {draftConflicts.length} staged change conflict{draftConflicts.length === 1 ? "" : "s"} need review.
                        </div>
                      ) : null}
                    </div>
                  </TabsContent>

                  <TabsContent
                    value="analyzer"
                    className="mt-0 animate-in fade-in slide-in-from-bottom-4 duration-500 xl:flex xl:min-h-0 xl:flex-1 xl:flex-col xl:overflow-auto"
                  >
                    <div className="xl:flex xl:min-h-full xl:flex-col xl:justify-center xl:pb-4">
                      <ScenarioAnalyzerDashboard />
                    </div>
                  </TabsContent>

                  <TabsContent
                    value="ml-forecasts"
                    className="mt-0 animate-in fade-in slide-in-from-bottom-4 duration-500 xl:flex xl:min-h-0 xl:flex-1 xl:flex-col xl:overflow-auto"
                  >
                    <div className="xl:flex xl:min-h-full xl:flex-col xl:justify-center xl:pb-4">
                      <MlForecastsDashboard />
                    </div>
                  </TabsContent>
                  </ErrorBoundary>
                </div>

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
              </div>
            ) : null}
          </div>
        </Tabs>

        {/* Modals */}
        <ErrorBoundary fallbackTitle="Modal error">
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
          optimizationSummary={latestOptimization}
          optimizationStats={optimizationStats}
          optimizationFinancials={optimizationFinancials}
          activeRun={activeRun}
          isOpen={uiStore.isSummaryModalOpen}
          onClose={uiStore.closeSummaryModal}
        />

        <Toaster position="bottom-center" richColors />
        </ErrorBoundary>
      </div>
    </div>
  );
}
