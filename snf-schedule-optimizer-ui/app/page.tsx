import React, { Suspense } from "react";
import DashboardShell from "@/components/dashboard-shell";
import ScheduleBoardContainer from "@/components/schedule-board/scheduling-board-container";

export default function HomePage() {
  return (
    <Suspense fallback={null}>
      <DashboardShell timelineView={<ScheduleBoardContainer />} />
    </Suspense>
  );
}
