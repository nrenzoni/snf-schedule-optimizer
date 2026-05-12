import test from "node:test";
import assert from "node:assert/strict";
import { calculateCellMetric } from "@/components/schedule-board/utils";
import { Shift, Staff } from "@/types/scheduler";

const staffList: Staff[] = [
  { id: "st1", name: "Alice", role: "RN", unitId: "U1", fte: 1 },
  { id: "st2", name: "Bob", role: "LPN", unitId: "U1", fte: 1 },
];

const shifts: Shift[] = [
  {
    id: "shift-1",
    staffId: "st1",
    dateStr: "2026-05-11",
    role: "RN",
    shiftType: "DAY",
  },
  {
    id: "shift-2",
    staffId: "st2",
    dateStr: "2026-05-11",
    role: "LPN",
    shiftType: "DAY",
    isOvertime: true,
  },
];

test("calculateCellMetric returns HPRD metrics for role view", () => {
  const metric = calculateCellMetric(
    shifts,
    { unitId: "U1" },
    "ROLE",
    "ROLE",
    staffList,
    "2026-05-11",
    "DAY",
  );

  assert.equal(metric.label, "0.40");
  assert.equal(metric.status, "critical");
});

test("calculateCellMetric returns budget metrics for budget view", () => {
  const metric = calculateCellMetric(
    shifts,
    { unitId: "U1" },
    "BUDGET",
    "BUDGET",
    staffList,
    "2026-05-11",
    "DAY",
  );

  assert.equal(metric.label, "$0.7k");
  assert.equal(metric.status, "critical");
});
