"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React, { useState } from "react";
import DashboardContent from "@/components/dashboard-content";

interface DashboardShellProps {
  timelineView: React.ReactNode; // <--- The "Slot" for Server Content
}

// 1. THE OUTER SHELL (Provider Only)
export default function DashboardShell({ timelineView }: DashboardShellProps) {
  // Create the client once per session
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      {/* We render the Content component here.
        Because it is a CHILD of Provider, it can access the QueryClient.
      */}
      <DashboardContent timelineView={timelineView} />
    </QueryClientProvider>
  );
}
