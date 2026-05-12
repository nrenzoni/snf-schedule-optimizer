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

  const { selectedFacility, scheduleCount } = useSchedulingStore(
    useShallow((state) => ({
      selectedFacility: state.selectedFacility,
      scheduleCount: state.scheduleMap.size,
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
      tone: "text-emerald-600 bg-emerald-50 ring-emerald-100",
    },
    {
      label: "Open Shifts",
      value: scheduleCount > 0 ? "7" : "--",
      detail: "Needs planner review",
      icon: AlertTriangle,
      tone: "text-amber-600 bg-amber-50 ring-amber-100",
    },
    {
      label: "Agency Hours",
      value: scheduleCount > 0 ? "-18%" : "--",
      detail: "Projected vs baseline",
      icon: TrendingDown,
      tone: "text-indigo-600 bg-indigo-50 ring-indigo-100",
    },
    {
      label: "Staff Mix",
      value: scheduleCount > 0 ? "82%" : "--",
      detail: "Internal team utilization",
      icon: Users,
      tone: "text-cyan-700 bg-cyan-50 ring-cyan-100",
    },
  ];

  const activeModuleLabel =
    activeModule === "scheduling"
      ? "Scheduling"
      : activeModule === "analyzer"
        ? "Scenario Analyzer"
        : "ML Forecasts";

  const isTimelineScheduling =
    activeModule === "scheduling" && viewMode === "timeline";

  const renderTabTrigger = (
    value: (typeof moduleOptions)[number],
    icon: React.ReactNode,
    label: string,
    isPulse = false,
  ) => {
    const isActive = activeModule === value;

      return (
        <TabsTrigger
          data-testid={`tab-${value}`}
          value={value}
          className={cn(
          "flex min-w-fit items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-bold h-auto transition-all sm:text-sm",
          "text-slate-500 hover:text-slate-800 hover:bg-white/70",
          "data-[state=active]:bg-slate-950 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-slate-900/10",
          value === "ml-forecasts" && isActive
            ? "data-[state=active]:bg-purple-700 data-[state=active]:text-white"
            : "data-[state=active]:text-white",
          isPulse &&
            showPulse &&
            "animate-pulse bg-purple-200 ring-2 ring-purple-500/50 hover:bg-purple-200/80",
        )}
      >
        {icon}
        <span>{label}</span>
      </TabsTrigger>
    );
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.16),transparent_34rem),linear-gradient(180deg,#f8fafc_0%,#eef2ff_45%,#f8fafc_100%)] p-2 font-sans md:p-3">
      <div
        className={cn(
          "mx-auto transition-all duration-300 ease-in-out",
          viewMode === "timeline" ? "max-w-[1800px]" : "max-w-4xl",
        )}
      >
        <DemoModeBanner />

        {isUsingFallbackApiBaseUrl ? (
          <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
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
          <div className="mb-2 overflow-hidden rounded-2xl border border-white/70 bg-white/85 p-2.5 shadow-lg shadow-indigo-950/5 backdrop-blur">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-indigo-600">
                  <Calendar size={15} />
                  Staffing Command Center
                </div>
                <div className="hidden h-5 w-px bg-slate-200 sm:block" />
                <h1 className="truncate text-sm font-black text-slate-950 sm:text-base">
                  {activeModuleLabel}
                </h1>
              </div>

              <div className="flex flex-col gap-2 lg:items-end">
                <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1 rounded-full border border-slate-200 bg-slate-100/80 p-1 shadow-inner lg:w-fit" data-testid="module-menu">
                  {renderTabTrigger("scheduling", <Calendar size={16} />, "Scheduling")}
                  {renderTabTrigger("analyzer", <BarChart2 size={16} />, "Scenario Analyzer")}
                  {renderTabTrigger("ml-forecasts", <Brain size={16} />, "ML Forecasts", true)}
                </TabsList>

                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-full bg-slate-950 px-3 py-1.5 text-xs text-slate-300 shadow-md shadow-slate-950/10 ring-1 ring-black/5">
                  <div>
                    <span className="font-bold text-white">Facility:</span>{" "}
                    {selectedFacility
                      ? `${selectedFacility.facilityId} (${selectedFacility.orgId})`
                      : isLoading
                        ? "Loading..."
                        : "None"}
                  </div>
                  <div>
                    <span className="font-bold text-white">Loaded days:</span>{" "}
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

                <div className={cn(
                  "grid gap-2 md:grid-cols-2 xl:grid-cols-4",
                  isTimelineScheduling && "rounded-2xl border border-white/70 bg-white/80 p-2 shadow-lg shadow-indigo-950/[0.03] backdrop-blur",
                )}>
                  {executiveMetrics.map((metric) => (
                    <div
                      key={metric.label}
                      className={cn(
                        "rounded-2xl border border-white/70 bg-white/85 shadow-lg shadow-slate-950/[0.03] backdrop-blur transition hover:-translate-y-0.5 hover:shadow-xl",
                        isTimelineScheduling ? "p-2.5" : "p-4",
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-400">
                            {metric.label}
                          </p>
                          <p className={cn(
                            "font-black tracking-tight text-slate-950",
                            isTimelineScheduling ? "mt-1 text-xl" : "mt-2 text-3xl",
                          )}>
                            {metric.value}
                          </p>
                        </div>
                        <div className={cn("rounded-2xl p-1.5 ring-1", metric.tone)}>
                          <metric.icon size={isTimelineScheduling ? 16 : 19} />
                        </div>
                      </div>
                      <p className={cn(
                        "font-medium text-slate-500",
                        isTimelineScheduling ? "mt-1 text-xs" : "mt-2 text-sm",
                      )}>
                        {metric.detail}
                      </p>
                    </div>
                  ))}
                </div>

                <div className="flex justify-end">
                  <div className="flex flex-wrap justify-end gap-2">
                    {viewMode === "timeline" ? (
                      <>
                        <button
                          data-testid="open-schedule-summary"
                          onClick={uiStore.openSummaryModal}
                          className="flex items-center gap-1 rounded-lg border border-indigo-200 bg-white px-3 py-2 text-sm font-semibold text-indigo-600 shadow-sm transition duration-200 hover:bg-indigo-50"
                        >
                          <ListChecks size={16} />
                          Summary
                        </button>
                        <button
                          data-testid="open-scheduling-config"
                          onClick={uiStore.openConfigModal}
                          className="flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-700 shadow-sm transition duration-200 hover:bg-gray-50"
                        >
                          <Settings size={16} />
                          Configure
                        </button>
                      </>
                    ) : null}
                  <div className="flex space-x-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
                    <button
                      data-testid="view-list"
                      onClick={() => setViewMode("list")}
                      className={cn(
                        "px-3 py-1.5 text-sm font-medium rounded-md flex items-center gap-2 transition-colors",
                        viewMode === "list"
                          ? "bg-indigo-50 text-indigo-600"
                          : "text-gray-500 hover:bg-gray-50",
                      )}
                    >
                      <LayoutList size={14} /> <span>List</span>
                    </button>
                    <button
                      data-testid="view-timeline"
                      onClick={() => setViewMode("timeline")}
                      className={cn(
                        "px-3 py-1.5 text-sm font-medium rounded-md flex items-center gap-2 transition-colors",
                        viewMode === "timeline"
                          ? "bg-indigo-50 text-indigo-600"
                          : "text-gray-500 hover:bg-gray-50",
                      )}
                    >
                      <GanttChartSquare size={14} /> <span>Timeline</span>
                    </button>
                  </div>
                  </div>
                </div>

                {viewMode === "list" ? (
                  <ScheduleListView />
                ) : (
                    <div className="h-[calc(100vh-170px)] min-h-[560px] rounded-2xl border border-white/80 bg-white/90 p-2 shadow-xl shadow-indigo-950/5 backdrop-blur">
                      {timelineView}
                    </div>
                )}
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
