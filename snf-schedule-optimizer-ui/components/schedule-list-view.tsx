import React from "react";
import {
  ChevronLeft,
  ChevronRight,
  ListChecks,
  Settings,
  Zap,
} from "lucide-react";
import { CalendarGrid } from "@/components/scheduling/calendar-grid";
import { useUIStore } from "@/store/uiStore";
import { useSchedulingStore } from "@/store/schedulingStore";
import { useShallow } from "zustand/react/shallow";
import ThreeDAssemblyLoader from "@/components/three-d-assembly-loader";
import { useScheduling } from "@/hooks/use-scheduling";
import { useSchedulingInitializer } from "@/hooks/use-scheduling-initializer";
import LoadingOverlay from "@/components/ui/loading-overlay";
import { ScheduleQueryError } from "@/hooks/use-schedule-query";
import DashboardEmptyState from "@/components/dashboard-empty-state";

// --- HELPERS (MUST BE COPIED OR MOVED) ---
// You should move the Spinner, DAYS_OF_WEEK, and monthYearFormatter helpers
// to a shared utility file or define them here for now.

const DAYS_OF_WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const monthYearFormatter = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "long",
});

function Spinner() {
  return (
    <svg
      className="animate-spin h-4 w-4 text-white"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      ></circle>
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      ></path>
    </svg>
  );
}

// --- END HELPERS ---

export default function ScheduleListView() {
  const {
    currentDate,
    calendarDays,
    selectedDay, // Used for highlighting in Grid if needed
    isTwoWeekView,
    toggleCalendarView,
    changeMonth,
    openShiftDetails,
    triggerOptimization, // Replaces handleOptimize
  } = useScheduling();

  const isOptimizing = useSchedulingStore((state) => state.isOptimizing);

  const { dataError, scheduleCount, selectedFacility } = useSchedulingStore(
    useShallow((state) => ({
      dataError: state.dataError,
      scheduleCount: state.scheduleMap.size,
      selectedFacility: state.selectedFacility,
    })),
  );

  const { isAppLoading } = useSchedulingInitializer();

  // 3. Consume Global UI Actions (Sidebars/Modals not related to scheduling specifics)
  const { openConfigModal, openSummaryModal } = useUIStore(
    useShallow((state) => ({
      openConfigModal: state.openConfigModal,
      openSummaryModal: state.openSummaryModal,
    })),
  );

  return (
    // WRAPPER FOR TRANSITION
    <div
      key="scheduling"
      className="relative animate-in fade-in slide-in-from-bottom-4 duration-500 min-h-[600px]"
    >
      {/* 5. RENDER THE OVERLAY */}
      {/* It sits on top of the content below because of absolute positioning */}
      <LoadingOverlay isVisible={isAppLoading} />

      {/* loader handled via React Portal or Fixed positioning, so it overlays automatically */}
      {/*<OptimizerLoader isLoading={isOptimizing}/>*/}
      <ThreeDAssemblyLoader isLoading={isOptimizing} />

      {/* --- EXISTING SCHEDULING MODULE --- */}
      <div className="max-w-5xl mx-auto bg-white shadow-xl rounded-xl p-4 sm:p-6 mb-6">
        <header className="mb-6 border-b pb-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <button
              data-testid="previous-month"
              onClick={() => changeMonth(-1)}
              disabled={isTwoWeekView}
              className={`p-2 rounded-full text-gray-700 hover:bg-gray-100 transition duration-150 ${isTwoWeekView ? "opacity-30 cursor-not-allowed" : ""}`}
              aria-label="Previous month"
            >
              <ChevronLeft size={24} />
            </button>

            <h2 className="text-2xl sm:text-3xl font-bold text-gray-800 tracking-tight">
              {monthYearFormatter.format(currentDate)}
            </h2>

            <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            {/* Optimize Button */}
            <button
              data-testid="optimize-schedule"
              onClick={triggerOptimization}
              disabled={isOptimizing}
              className={`py-2 px-3 text-sm font-semibold rounded-lg shadow-sm transition duration-200 flex items-center gap-2 whitespace-nowrap
                                ${
                                  isOptimizing
                                    ? "bg-indigo-400 text-white cursor-not-allowed"
                                    : "bg-indigo-600 text-white hover:bg-indigo-700"
                                }`}
            >
              {isOptimizing ? <Spinner /> : <Zap size={16} />}
              <span>{isOptimizing ? "Optimizing..." : "Optimize"}</span>
            </button>

            {/* Summary Button */}
            <button
              data-testid="open-schedule-summary"
              onClick={openSummaryModal}
              className={`py-2 px-3 text-sm font-semibold rounded-lg shadow-sm border transition duration-200 bg-white text-indigo-600 hover:bg-indigo-50 border-indigo-200 flex items-center gap-1`}
            >
              <ListChecks size={16} />
              Summary
            </button>

            {/* Configure Button */}
            <button
              data-testid="open-scheduling-config"
              onClick={openConfigModal}
              className={`py-2 px-3 text-sm font-semibold rounded-lg shadow-sm border transition duration-200 bg-white text-gray-700 hover:bg-gray-50 border-gray-200 flex items-center gap-1`}
            >
              <Settings size={16} />
              Configure
            </button>

            {/* View Toggle Button */}
            <button
              data-testid="toggle-calendar-view"
              onClick={toggleCalendarView}
              className={`py-2 px-3 text-sm font-semibold rounded-lg shadow-sm border transition duration-200
                            ${
                              isTwoWeekView
                                ? "bg-indigo-600 text-white hover:bg-indigo-700 border-transparent"
                                : "bg-white text-gray-700 hover:bg-gray-50 border-gray-200"
                            }`}
            >
              {isTwoWeekView ? "View: 2 Week" : "View: Month"}
            </button>

            {/* Chevron Right Button */}
            <button
              data-testid="next-month"
              onClick={() => changeMonth(1)}
              disabled={isTwoWeekView}
              className={`p-2 rounded-full text-gray-700 hover:bg-gray-100 transition duration-150 ${isTwoWeekView ? "opacity-30 cursor-not-allowed" : ""}`}
              aria-label="Next month"
            >
              <ChevronRight size={24} />
            </button>
            </div>
          </div>
        </header>

        <div className="mb-4 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600 ring-1 ring-slate-200">
          <span className="font-semibold text-slate-900">Current facility:</span>{" "}
          {selectedFacility
            ? `${selectedFacility.facilityId} (${selectedFacility.orgId})`
            : "Waiting for facility context"}
        </div>

        {dataError ? (
          <DashboardEmptyState
            title={
              dataError instanceof ScheduleQueryError &&
              dataError.code === "NO_FACILITIES"
                ? "No facilities available"
                : "Schedule data is unavailable"
            }
            description={dataError.message}
          />
        ) : null}

        {!dataError && !isAppLoading && scheduleCount === 0 ? (
          <DashboardEmptyState
            title="No schedules returned"
            description="The selected period has no schedule data yet. Retry from the dashboard banner or switch to another month."
          />
        ) : null}

        {/* Weekday Names */}
        <div className="grid grid-cols-7 text-center font-semibold text-xs uppercase tracking-wide text-gray-500 mb-2">
          {DAYS_OF_WEEK.map((day) => (
            <div key={day} className="py-2">
              {day}
            </div>
          ))}
        </div>

        {/* Calendar Grid Component */}
        <CalendarGrid
          calendarDays={calendarDays}
          openShiftDetails={openShiftDetails}
          isTwoWeekView={isTwoWeekView}
          selectedDayDateString={selectedDay?.dateString || null}
        />

        {/* Legend */}
        <div className="mt-8 pt-4 border-t flex flex-wrap justify-center gap-6 text-sm text-gray-600">
          {/* 🟢 Ideal: 100% and above */}
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-green-500 shadow-sm"></span>
            <span>100%+ HPRD Covered (Ideal)</span>
          </div>

          {/* 🟡 Warning: 70% to 99% */}
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-yellow-400 shadow-sm"></span>
            <span>70% - 99% HPRD Covered (Warning)</span>
          </div>

          {/* 🔴 Critical: Below 70% */}
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-red-500 shadow-sm"></span>
            <span>&lt;70% HPRD Covered (Critical)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
