import React, { Suspense } from "react";
import AppShellSkeleton from "@/components/app-shell-skeleton";
import DashboardShell from "@/components/dashboard-shell";
import ScheduleBoardContainer from "@/components/schedule-board/scheduling-board-container";

export default function HomePage() {
  return (
    <Suspense fallback={<AppShellSkeleton />}>
      <DashboardShell timelineView={<ScheduleBoardContainer />} />
    </Suspense>
  );
}
