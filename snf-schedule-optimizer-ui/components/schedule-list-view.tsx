import React from "react";
import { useRouter } from "next/navigation";
import {
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { CalendarGrid } from "@/components/scheduling/calendar-grid";
import { useSchedulingStore } from "@/store/schedulingStore";
import { useShallow } from "zustand/react/shallow";
import { useScheduling } from "@/hooks/use-scheduling";
import { useSchedulingInitializer } from "@/hooks/use-scheduling-initializer";
import LoadingOverlay from "@/components/ui/loading-overlay";
import { ScheduleQueryError } from "@/hooks/use-schedule-query";
import DashboardEmptyState from "@/components/dashboard-empty-state";
import { cn } from "@/lib/utils";
import { iconButtonVariants } from "@/components/ui/styles";
import dynamic from "next/dynamic";

const ThreeDAssemblyLoader = dynamic(
  () => import("@/components/three-d-assembly-loader"),
  { ssr: false },
);

const DAYS_OF_WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const monthYearFormatter = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "long",
});

export default function ScheduleListView() {
  const router = useRouter();

  const {
    currentDate,
    calendarDays,
    selectedDay, // Used for highlighting in Grid if needed
    isTwoWeekView,
    toggleCalendarView,
    changeMonth,
    openShiftDetails,
    isRunActive,
  } = useScheduling();

  const { activeRun, dataError, scheduleCount, selectedFacility } = useSchedulingStore(
    useShallow((state) => ({
      activeRun: state.activeRun,
      dataError: state.dataError,
      scheduleCount: state.effectiveScheduleMap.size,
      selectedFacility: state.selectedFacility,
    })),
  );

  const { isAppLoading } = useSchedulingInitializer();

  return (
    // WRAPPER FOR TRANSITION
    <div
      key="scheduling"
      className="relative min-h-[600px] animate-in fade-in slide-in-from-bottom-4 duration-500"
    >
      <LoadingOverlay isVisible={isAppLoading && !isRunActive && scheduleCount > 0} />

      {/* --- EXISTING SCHEDULING MODULE --- */}
      <div className="app-card mb-6 p-4 sm:p-6">
        <header className="mb-6 border-b border-slate-200/70 pb-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <button
              data-testid="previous-month"
              onClick={() => changeMonth(-1)}
              disabled={isTwoWeekView}
              className={iconButtonVariants({
                tone: "soft",
                disabled: isTwoWeekView,
              })}
              aria-label="Previous month"
            >
              <ChevronLeft size={24} />
            </button>

            <h2 className="app-title text-2xl sm:text-3xl">
              {monthYearFormatter.format(currentDate)}
            </h2>

            <div className="flex flex-wrap items-center gap-2 lg:justify-end">
              <button
                data-testid="toggle-calendar-view"
                onClick={toggleCalendarView}
                className={cn(
                  "rounded-full border px-3 py-2 text-sm font-bold shadow-sm transition duration-200",
                  isTwoWeekView
                    ? "border-transparent bg-primary text-primary-foreground hover:bg-primary/90"
                    : "border-input bg-card text-foreground hover:bg-accent hover:text-primary",
                )}
              >
                {isTwoWeekView ? "View: 2 Week" : "View: Month"}
              </button>

              <button
                data-testid="next-month"
                onClick={() => changeMonth(1)}
                disabled={isTwoWeekView}
                className={iconButtonVariants({
                  tone: "soft",
                  disabled: isTwoWeekView,
                })}
                aria-label="Next month"
              >
                <ChevronRight size={24} />
              </button>
            </div>
          </div>
        </header>

        <div className="app-soft-panel mb-4 px-4 py-3 text-sm text-slate-600">
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
            title="No schedule for this month"
            description="No schedule has been created for this month. Try another month or switch back to a populated month."
            secondaryActionLabel="Go to current month"
            secondaryOnAction={() => router.push("/schedule")}
          />
        ) : null}

        <div className="relative overflow-hidden rounded-lg">
          <ThreeDAssemblyLoader
            isLoading={isRunActive}
            mode="inline"
            progressPercent={activeRun?.progressPercent}
            message={activeRun?.statusMessage || undefined}
          />

          {/* Weekday Names */}
          <div className="mb-2 grid grid-cols-7 text-center text-xs font-black uppercase tracking-[0.16em] text-slate-400">
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
          <div className="mt-8 flex flex-wrap justify-center gap-6 border-t border-slate-200/70 pt-4 text-sm text-slate-600">
            <div className="flex items-center space-x-2">
              <span className="h-3 w-3 rounded-full bg-green-500 shadow-sm" />
              <span>100%+ HPRD Covered (Ideal)</span>
            </div>

            <div className="flex items-center space-x-2">
              <span className="h-3 w-3 rounded-full bg-amber-400 shadow-sm" />
              <span>70% - 99% HPRD Covered (Warning)</span>
            </div>

            <div className="flex items-center space-x-2">
              <span className="h-3 w-3 rounded-full bg-red-500 shadow-sm" />
              <span>&lt;70% HPRD Covered (Critical)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
