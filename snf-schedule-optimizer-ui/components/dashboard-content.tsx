"use client";

import { useUIStore } from "@/store/uiStore";
import { useShallow } from "zustand/react/shallow";
import React, { Suspense, useEffect, useMemo, useState } from "react";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import ScheduleListView from "@/components/schedule-list-view";
import { Toaster } from "@/components/ui/sonner";
import ErrorBoundary from "@/components/error-boundary";
import ScenarioAnalyzerDashboard from "@/components/scenario-analyzer-dashboard";
import ShiftModal from "@/components/modals/shift-modal";
import { SchedulingConfigModal } from "@/components/modals/scheduling-config-modal";
import { ScheduleSummaryModal } from "@/components/modals/schedule-summary-modal";
import MlForecastsDashboard from "@/components/ml-forecasts-dashboard";
import { useScheduleData } from "@/hooks/use-schedule-query";
import { parseAsString, parseAsStringLiteral, useQueryState } from "nuqs";
import { getTodayString } from "@/lib/scheduling-logic";
import { useScheduling } from "@/hooks/use-scheduling";
import { useOptimizationRunSync } from "@/hooks/use-optimization-run-sync";
import NurseDetailsPanel from "@/components/nurse-details-panel";
import DashboardEmptyState from "@/components/dashboard-empty-state";
import { useSchedulingStore } from "@/store/schedulingStore";
import { ScheduleQueryError } from "@/hooks/use-schedule-query";
import DashboardTabs, { moduleOptions, type ModuleOption } from "@/components/dashboard-tabs";
import DashboardControls from "@/components/dashboard-controls";
import DashboardMetrics from "@/components/dashboard-metrics";
import { UIPatchConflict } from "@/types/scheduling";

export const viewOptions = ["list", "timeline"] as const;

interface DashboardShellProps {
  timelineView: React.ReactNode;
}

function DashboardErrorState({
  error,
  onRetry,
}: {
  error: Error;
  onRetry: () => void;
}) {
  return (
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
      onAction={onRetry}
    />
  );
}

function DashboardEmptySchedule({
  onReload,
}: {
  onReload: () => void;
}) {
  return (
    <DashboardEmptyState
      title="No schedule data returned"
      description="The API responded successfully but did not return any days for the selected month. Try another month or retry the query."
      actionLabel="Reload month"
      onAction={onReload}
    />
  );
}

interface DashboardMainLayoutProps {
  timelineView: React.ReactNode;
  scheduleCount: number;
  isLoading: boolean;
  hasNewerVersion: boolean;
  latestKnownScheduleVersion: number;
  draftPatchCount: number;
  draftConflicts: UIPatchConflict[];
  clearDraft: () => void;
  triggerOptimization: (allowOverwrite?: boolean) => Promise<void>;
  isRunActive: boolean;
  activeRun: {
    progressPercent: number;
    stage?: string;
    statusMessage?: string;
  } | null;
  optimizeButtonFillWidth: string;
  openSummaryModal: () => void;
  openConfigModal: () => void;
  viewMode: (typeof viewOptions)[number];
  setViewMode: (value: (typeof viewOptions)[number]) => Promise<URLSearchParams>;
  activeModule: ModuleOption;
  refetch: () => void;
}

function ControlsSkeleton() {
  return <div className="h-12 animate-pulse rounded bg-muted" />;
}
function BoardSkeleton() {
  return <div className="h-[560px] animate-pulse rounded bg-muted" />;
}
function MetricsSkeleton() {
  return <div className="h-64 animate-pulse rounded bg-muted" />;
}

function DashboardMainLayout({
  timelineView,
  scheduleCount,
  isLoading,
  hasNewerVersion,
  latestKnownScheduleVersion,
  draftPatchCount,
  draftConflicts,
  clearDraft,
  triggerOptimization,
  isRunActive,
  activeRun,
  optimizeButtonFillWidth,
  openSummaryModal,
  openConfigModal,
  viewMode,
  setViewMode,
  activeModule,
  refetch,
}: DashboardMainLayoutProps) {
  return (
    <div className="grid items-start gap-3 xl:h-full xl:min-h-0 xl:items-stretch 2xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 xl:flex xl:min-h-0 xl:flex-col">
        <ErrorBoundary fallbackTitle="Schedule content error">
        <TabsContent
          value="scheduling"
          className="mt-0 xl:flex xl:min-h-0 xl:flex-1 xl:flex-col xl:overflow-hidden"
        >
          <div className="space-y-2 xl:flex xl:min-h-0 xl:flex-1 xl:flex-col xl:gap-2 xl:space-y-0">
            {!isLoading && scheduleCount === 0 ? (
              <DashboardEmptySchedule
                onReload={() => {
                  void refetch();
                }}
              />
            ) : null}

            <Suspense fallback={<ControlsSkeleton />}>
              <DashboardControls
                hasNewerVersion={hasNewerVersion}
                latestKnownScheduleVersion={latestKnownScheduleVersion}
                draftPatchCount={draftPatchCount}
                draftConflicts={draftConflicts}
                clearDraft={clearDraft}
                triggerOptimization={triggerOptimization}
                isRunActive={isRunActive}
                activeRun={activeRun}
                optimizeButtonFillWidth={optimizeButtonFillWidth}
                uiStore={{ openSummaryModal, openConfigModal }}
                viewMode={viewMode}
                setViewMode={setViewMode}
              />
            </Suspense>

            <Suspense fallback={<BoardSkeleton />}>
              {viewMode === "list" ? (
                <div className="xl:min-h-0 xl:flex-1 xl:overflow-auto xl:pb-4">
                  <ScheduleListView />
                </div>
              ) : (
                <div className="app-card min-h-[560px] p-2 xl:min-h-0 xl:flex-1 xl:overflow-hidden">
                  <div className="xl:flex xl:h-full xl:min-h-0 xl:flex-col">{timelineView}</div>
                </div>
              )}
            </Suspense>
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

      <Suspense fallback={<MetricsSkeleton />}>
        <DashboardMetrics activeModule={activeModule} />
      </Suspense>
    </div>
  );
}

export default function DashboardContent({
  timelineView,
}: DashboardShellProps) {
  const [anchorDateStr] = useQueryState(
    "anchor",
    parseAsString.withDefault(getTodayString()),
  );

  const currentViewAnchorDate = useMemo(
    () => new Date(anchorDateStr),
    [anchorDateStr],
  );

  const [activeModule, setActiveModule] = useQueryState(
    "tab",
    parseAsStringLiteral(moduleOptions).withDefault("scheduling"),
  );

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

  const scheduleData = useScheduleData(currentViewAnchorDate);

  const {
    scheduleMap,
    selectedFacility,
    latestOptimization,
    optimizationStats,
    optimizationFinancials,
    isLoading,
    error,
    refetch,
  } = scheduleData;

  const scheduleCount = scheduleMap.size;

  const {
    activeRun,
    hasNewerVersion,
    latestKnownScheduleVersion,
    draftPatchCount,
    draftConflicts,
    schedulerSettings,
  } = useSchedulingStore(
    useShallow((state) => ({
      activeRun: state.activeRun,
      hasNewerVersion: state.hasNewerVersion,
      latestKnownScheduleVersion: state.latestKnownScheduleVersion,
      draftPatchCount: state.draftState.patches.length,
      draftConflicts: state.draftState.conflicts,
      schedulerSettings: state.schedulerSettings,
    })),
  );

  const replaceScheduleData = useSchedulingStore((s) => s.replaceScheduleData);
  const setScheduleData = useSchedulingStore((s) => s.setScheduleData);

  useEffect(() => {
    if (scheduleData.status === "success" && scheduleData.data) {
      replaceScheduleData({
        map: scheduleData.data.scheduleMap,
        facility: scheduleData.data.selectedFacility,
        scheduleId: scheduleData.data.scheduleId,
        scheduleVersion: scheduleData.data.scheduleVersion,
        latestOptimization: scheduleData.data.latestOptimization,
        optimizationStats: scheduleData.data.optimizationStats,
        optimizationFinancials: scheduleData.data.optimizationFinancials,
        activeRun: scheduleData.data.activeRun,
        updatedAt: scheduleData.data.updatedAt,
      });
    } else if (scheduleData.status === "error") {
      const err = scheduleData.error instanceof Error ? scheduleData.error : scheduleData.error ? new Error(String(scheduleData.error)) : null;
      setScheduleData(new Map(), false, err, null);
    } else if (scheduleData.status === "pending") {
      setScheduleData(new Map(), true, null, null);
    }
  }, [
    scheduleData.status,
    scheduleData.data,
    scheduleData.error,
    replaceScheduleData,
    setScheduleData,
  ]);

  const {
    selectedDay,
    selectedShift,
    selectedNurse,
    isModalVisible,

    closeModal,
    selectShift,
    openNurseDetails,
    closeNurseDetails,
    removeNurseFromShift,
    addNurseToShift,

    triggerOptimization,
    clearDraft,
    isRunActive,
    updateSchedulerSettings,
  } = useScheduling();

  const [showPulse, setShowPulse] = useState(true);

  const optimizeButtonFillWidth = activeRun
    ? `${Math.max(0, Math.min(100, activeRun.progressPercent))}%`
    : "0%";

  useOptimizationRunSync();

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowPulse(false);
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="app-bg min-h-screen p-2 font-sans md:p-3 xl:h-screen xl:overflow-hidden">
      <div className="mx-auto max-w-[1800px] xl:flex xl:h-full xl:flex-col">
        <Tabs
          value={activeModule}
          onValueChange={(value) => void setActiveModule(value as ModuleOption)}
          className="w-full xl:min-h-0 xl:flex-1 xl:overflow-hidden"
        >
          <DashboardTabs
            selectedFacility={selectedFacility}
            isLoading={isLoading}
            scheduleCount={scheduleCount}
            showPulse={showPulse}
          />

          <div className="min-h-[600px] xl:min-h-0 xl:flex-1 xl:overflow-hidden xl:pb-4">
            {error ? (
              <DashboardErrorState
                error={error}
                onRetry={() => {
                  void refetch();
                }}
              />
            ) : (
              <DashboardMainLayout
                timelineView={timelineView}
                scheduleCount={scheduleCount}
                isLoading={isLoading}
                hasNewerVersion={hasNewerVersion}
                latestKnownScheduleVersion={latestKnownScheduleVersion}
                draftPatchCount={draftPatchCount}
                draftConflicts={draftConflicts}
                clearDraft={clearDraft}
                triggerOptimization={triggerOptimization}
                isRunActive={isRunActive}
                activeRun={activeRun}
                optimizeButtonFillWidth={optimizeButtonFillWidth}
                openSummaryModal={uiStore.openSummaryModal}
                openConfigModal={uiStore.openConfigModal}
                viewMode={viewMode}
                setViewMode={setViewMode}
                activeModule={activeModule}
                refetch={refetch}
              />
            )}
          </div>
        </Tabs>

        <ErrorBoundary fallbackTitle="Modal error">
        <ShiftModal
          selectedDay={selectedDay}
          selectedShift={selectedShift}
          selectedNurse={selectedNurse}
          isModalVisible={isModalVisible}
          closeModal={closeModal}
          selectShift={selectShift}
          openNurseDetails={openNurseDetails}
        >
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
