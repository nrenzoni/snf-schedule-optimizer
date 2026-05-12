// 1. Define Server-Side Fetching Logic
import { Shift, Staff } from "@/types/scheduler";
import ScheduleBoard from "@/components/schedule-board/schedule-board";

async function getScheduleData() {
  const staffList: Staff[] = [
    { id: "st1", name: "Alicia Bennett, RN", role: "RN", unitId: "U1", fte: 1.0 },
    { id: "st2", name: "Marcus Rivera, RN", role: "RN", unitId: "U2", fte: 1.0 },
    { id: "st3", name: "Priya Patel, RN Agency", role: "RN", unitId: "U4", fte: 0.8 },
    { id: "st4", name: "Danielle Brooks, LPN", role: "LPN", unitId: "U1", fte: 1.0 },
    { id: "st5", name: "Jorge Santos, LPN", role: "LPN", unitId: "U2", fte: 1.0 },
    { id: "st6", name: "Nina Nguyen, LPN", role: "LPN", unitId: "U3", fte: 0.9 },
    { id: "st7", name: "Keisha Carter, CNA", role: "CNA", unitId: "U1", fte: 1.0 },
    { id: "st8", name: "Andre Jackson, CNA", role: "CNA", unitId: "U2", fte: 1.0 },
    { id: "st9", name: "Mei Kim, CNA Agency", role: "CNA", unitId: "U3", fte: 0.8 },
    { id: "st10", name: "Hannah Miller, CNA", role: "CNA", unitId: "U4", fte: 1.0 },
    { id: "st11", name: "Tessa Garcia, PT", role: "THERAPIST", unitId: "U1", fte: 0.6 },
  ];

  const firstVisibleDay = new Date();
  firstVisibleDay.setDate(firstVisibleDay.getDate() - 2);

  const formatDate = (date: Date) => date.toISOString().split("T")[0];

  const initialShifts: Shift[] = [
    {
      id: "s1",
      staffId: "st1",
      dateStr: formatDate(firstVisibleDay),
      shiftType: "DAY",
      role: "RN",
    },
    {
      id: "s2",
      staffId: "st5",
      dateStr: formatDate(firstVisibleDay),
      shiftType: "EVE",
      role: "LPN",
    },
    {
      id: "s3",
      staffId: "st9",
      dateStr: formatDate(firstVisibleDay),
      shiftType: "NIGHT",
      role: "CNA",
      isAgency: true,
    },
  ];

  const units = [
    { id: "U1", label: "Short-Term Rehab" },
    { id: "U2", label: "Long-Term Care" },
    { id: "U3", label: "Memory Care" },
    { id: "U4", label: "Skilled/Subacute" },
  ];

  const dates = Array.from({ length: 91 }).map((_, i) => {
    const date = new Date(firstVisibleDay);
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
