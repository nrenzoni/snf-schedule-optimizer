import React, { Suspense } from "react";
import DashboardShell from "@/components/dashboard-shell";
import ScheduleBoardContainer from "@/components/schedule-board/scheduling-board-container";
import AppShellSkeleton from "@/components/app-shell-skeleton";
import ErrorBoundary from "@/components/error-boundary";

export default function SchedulePage() {
  return (
    <Suspense fallback={<AppShellSkeleton />}>
      <ErrorBoundary fallbackTitle="Schedule board crashed">
        <DashboardShell timelineView={<ScheduleBoardContainer />} />
      </ErrorBoundary>
    </Suspense>
  );
}
