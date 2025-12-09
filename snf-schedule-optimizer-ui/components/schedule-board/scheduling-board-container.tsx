// 1. Define Server-Side Fetching Logic
import { Shift, Staff } from "@/types/scheduler";
import ScheduleBoard from "@/components/schedule-board/schedule-board";

async function getScheduleData() {
  // Simulate DB Fetch
  // await db.connect()...

  const staffList: Staff[] = [
    { id: "st1", name: "Alice Johnson", role: "RN", unitId: "U1", fte: 1.0 },
    { id: "st2", name: "Bob Smith", role: "RN", unitId: "U2", fte: 0.8 },
    { id: "st3", name: "Carol White", role: "LPN", unitId: "U1", fte: 1.0 },
    { id: "st4", name: "David Brown", role: "CNA", unitId: "U2", fte: 1.0 },
    { id: "st5", name: "Eve Davis", role: "THERAPIST", unitId: "U1", fte: 0.5 },
  ];

  const initialShifts: Shift[] = [
    {
      id: "s1",
      staffId: "st1",
      dateStr: new Date().toISOString().split("T")[0],
      shiftType: "DAY",
      role: "RN",
    },
  ];

  const units = [
    { id: "U1", label: "1st Floor - Rehab" },
    { id: "U2", label: "2nd Floor - LTC" },
  ];

  const dates = Array.from({ length: 14 }).map((_, i) => {
    const date = new Date();
    date.setDate(date.getDate() + i);
    return date;
  });

  return { staffList, initialShifts, units, dates };
}

// 2. Export the Async Server Component
export default async function ScheduleBoardContainer() {
  const data = await getScheduleData();

  return (
    <ScheduleBoard
      staffList={data.staffList}
      initialShifts={data.initialShifts}
      units={data.units}
      dates={data.dates}
    />
  );
}
