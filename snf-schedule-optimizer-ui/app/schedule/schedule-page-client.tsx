"use client";

import DashboardShell from "@/components/dashboard-shell";
import ScheduleBoardContainer from "@/components/schedule-board/scheduling-board-container";
import ErrorBoundary from "@/components/error-boundary";

export default function SchedulePageClient() {
  return (
    <ErrorBoundary fallbackTitle="Schedule board crashed">
      <DashboardShell timelineView={<ScheduleBoardContainer />} />
    </ErrorBoundary>
  );
}
