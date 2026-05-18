import { Suspense } from "react";
import AppShellSkeleton from "@/components/app-shell-skeleton";
import SchedulePageClient from "./schedule-page-client";

export default function SchedulePage() {
  return (
    <Suspense fallback={<AppShellSkeleton />}>
      <SchedulePageClient />
    </Suspense>
  );
}
