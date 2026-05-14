import React, { Suspense } from "react";
import DashboardShell from "@/components/dashboard-shell";
import ScheduleBoardContainer from "@/components/schedule-board/scheduling-board-container";
import AppShellSkeleton from "@/components/app-shell-skeleton";

export default function SchedulePage() {
  return (
    <Suspense fallback={<AppShellSkeleton />}>
      <DashboardShell timelineView={<ScheduleBoardContainer />} />
    </Suspense>
  );
}
