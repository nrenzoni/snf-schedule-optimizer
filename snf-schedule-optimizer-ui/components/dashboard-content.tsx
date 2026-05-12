"use client";

import { useUIStore } from "@/store/uiStore";
import { useShallow } from "zustand/react/shallow";
import React, { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  BarChart2,
  Brain,
  Calendar,
  GanttChartSquare,
  LayoutList,
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
    parseAsStringLiteral(viewOptions).withDefault("list"),
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

  const { selectedFacility, resetDemoState, scheduleCount } = useSchedulingStore(
    useShallow((state) => ({
      selectedFacility: state.selectedFacility,
      resetDemoState: state.resetDemoState,
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

  const renderTabTrigger = (
    value: (typeof moduleOptions)[number],
    icon: React.ReactNode,
    label: string,
    isPulse = false,
  ) => {
    const isActive = activeModule === value;

    return (
      <TabsTrigger
        value={value}
        className={cn(
          "flex items-center space-x-2 px-4 md:px-6 py-2.5 rounded-lg text-sm font-bold h-auto transition-all",
          "text-gray-500 hover:text-gray-700 hover:bg-gray-200/50",
          "data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:ring-1 data-[state=active]:ring-black/5",
          value === "ml-forecasts" && isActive
            ? "data-[state=active]:text-purple-600"
            : "data-[state=active]:text-indigo-600",
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
    <div className="p-4 md:p-8 bg-gray-50 min-h-screen font-sans">
      <div
        className={cn(
          "mx-auto transition-all duration-300 ease-in-out",
          viewMode === "timeline" ? "max-w-[1800px]" : "max-w-4xl",
        )}
      >
        <DemoModeBanner
          onReset={() => {
            resetDemoState();
            void refetch();
          }}
        />

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
          {/* Navigation Bar */}
          <div className="flex justify-center mb-8 relative">
            <TabsList className="bg-gray-200 p-1.5 rounded-xl flex space-x-1 shadow-inner overflow-x-auto max-w-full z-10 h-auto">
              {renderTabTrigger(
                "scheduling",
                <Calendar size={16} />,
                "Scheduling",
              )}
              {renderTabTrigger(
                "analyzer",
                <BarChart2 size={16} />,
                "Scenario Analyzer",
              )}
              {renderTabTrigger(
                "ml-forecasts",
                <Brain size={16} />,
                "ML Forecasts",
                true,
              )}
            </TabsList>
          </div>

          {/*Tabs Content*/}
          <div className="min-h-[600px]">
            <div className="mb-4 flex flex-col gap-2 rounded-xl bg-white px-4 py-3 text-sm text-slate-600 shadow-sm ring-1 ring-black/5 md:flex-row md:items-center md:justify-between">
              <div>
                <span className="font-semibold text-slate-900">Facility:</span>{" "}
                {selectedFacility
                  ? `${selectedFacility.facilityId} (${selectedFacility.orgId})`
                  : isLoading
                    ? "Loading facility context..."
                    : "No facility selected"}
              </div>
              <div>
                <span className="font-semibold text-slate-900">Loaded days:</span>{" "}
                {scheduleCount}
              </div>
            </div>

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
              <div className="space-y-4">
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
                  <div className="bg-white border rounded-lg p-1 flex space-x-1">
                    <button
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

                {viewMode === "list" ? (
                  <ScheduleListView />
                ) : (
                  <div className="bg-white rounded-xl shadow-sm border p-4 h-[calc(100vh-250px)]">
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
