import { Shift, Staff } from "@/types/scheduler";
import { addDays, format, startOfToday } from "date-fns";
import ScheduleBoard from "@/components/schedule-board/schedule-board";
import QueryProvider from "@/components/query-provider";
import { Toaster } from "@/components/ui/sonner";

async function getScheduleData() {
  // In a real app, this is: await db.query(...)
  const staffList: Staff[] = [
    { id: "st1", name: "Alice Johnson", role: "RN", unitId: "U1", fte: 1.0 },
    { id: "st2", name: "Bob Smith", role: "RN", unitId: "U2", fte: 0.8 },
    // ...
  ];

  const startDate = startOfToday();
  const dates = Array.from({ length: 5 }, (_, i) => addDays(startDate, i));

  const shifts: Shift[] = [
    {
      id: "s1",
      staffId: "st1",
      dateStr: format(dates[0], "yyyy-MM-dd"),
      shiftType: "DAY",
      role: "RN",
    },
    {
      id: "s2",
      staffId: "st1",
      dateStr: format(dates[1], "yyyy-MM-dd"),
      shiftType: "DAY",
      role: "RN",
      isOvertime: true,
    },
    {
      id: "s3",
      staffId: "st3",
      dateStr: format(dates[0], "yyyy-MM-dd"),
      shiftType: "NIGHT",
      role: "LPN",
    },
  ];

  const units = [
    { id: "U1", label: "1st Floor - Rehab" },
    { id: "U2", label: "2nd Floor - LTC" },
  ];

  return { staffList, shifts, units, dates };
}

export default async function SchedulePage() {
  // 1. Fetch data on the Server
  const data = await getScheduleData();

  return (
    <div className="h-screen w-full bg-gray-50 p-4">
      {/* 2. Pass data to Client Component */}
      <QueryProvider>
        <ScheduleBoard
          staffList={data.staffList}
          initialShifts={data.shifts}
          units={data.units}
          dates={data.dates}
        />
      </QueryProvider>

      {/* Toaster can be here or in layout.tsx */}
      <Toaster position="bottom-center" richColors />
    </div>
  );
}
