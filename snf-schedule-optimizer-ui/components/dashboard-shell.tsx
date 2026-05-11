"use client";

import React from "react";
import DashboardContent from "@/components/dashboard-content";
import QueryProvider from "@/components/query-provider";

interface DashboardShellProps {
  timelineView: React.ReactNode; // <--- The "Slot" for Server Content
}

// 1. THE OUTER SHELL (Provider Only)
export default function DashboardShell({ timelineView }: DashboardShellProps) {
  return (
    <QueryProvider>
      {/* We render the Content component here.
        Because it is a CHILD of Provider, it can access the QueryClient.
      */}
      <DashboardContent timelineView={timelineView} />
    </QueryProvider>
  );
}
