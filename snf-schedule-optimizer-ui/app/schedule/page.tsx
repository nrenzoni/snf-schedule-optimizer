import React, { Suspense } from "react";
import DashboardShell from "@/components/dashboard-shell";
import ScheduleBoardContainer from "@/components/schedule-board/scheduling-board-container";
import ThreeDAssemblyLoader from "@/components/three-d-assembly-loader";

export default function SchedulePage() {
  return (
    <Suspense fallback={<ThreeDAssemblyLoader isLoading />}>
      <DashboardShell timelineView={<ScheduleBoardContainer />} />
    </Suspense>
  );
}
