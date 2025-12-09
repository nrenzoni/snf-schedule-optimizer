// "use client";

import React from "react";
import DashboardShell from "@/components/dashboard-shell";
import ScheduleBoardContainer from "@/components/schedule-board/scheduling-board-container";

export default () => {
  return <DashboardShell timelineView={<ScheduleBoardContainer />} />;
};
