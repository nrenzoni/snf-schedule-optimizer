import { useMemo } from "react";
import { useSchedulingStore } from "@/store/schedulingStore";
import { useShallow } from "zustand/react/shallow";
import {
  AlertTriangle,
  BarChart2,
  Brain,
  CheckCircle2,
  TrendingDown,
  Users,
} from "lucide-react";
import type { ModuleOption } from "@/components/dashboard-tabs";
import type { ScheduleMap } from "@/types/scheduling";

export type MetricTone = "success" | "warning" | "neutral";

export interface ExecutiveMetric {
  label: string;
  value: string;
  detail: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  tone: MetricTone;
}

const MODULE_ICONS: Record<ModuleOption, React.ComponentType<{ size?: number; className?: string }>[]> = {
  scheduling: [CheckCircle2, AlertTriangle, TrendingDown, Users],
  analyzer: [BarChart2, Users, CheckCircle2, AlertTriangle],
  "ml-forecasts": [TrendingDown, Users, CheckCircle2, Brain],
};

function getEmptyMetrics(activeModule: ModuleOption): ExecutiveMetric[] {
  const labels: Record<ModuleOption, string[]> = {
    scheduling: ["Coverage Score", "Open Shifts", "Agency Hours", "Staff Mix"],
    analyzer: ["Labor Spend", "Agency Utilization", "Avg HPPD", "Overtime Risk"],
    "ml-forecasts": ["Weekend HPPD", "Burnout Flags", "Compliance Score", "Pending Actions"],
  };

  return labels[activeModule].map((label, i) => ({
    label,
    value: "--",
    detail: "No schedule data loaded.",
    icon: MODULE_ICONS[activeModule][i],
    tone: "neutral" as MetricTone,
  }));
}

function computeSchedulingMetrics(map: ScheduleMap): ExecutiveMetric[] {
  let totalRequiredHours = 0;
  let totalActualHours = 0;
  let openShiftCount = 0;
  let agencyHours = 0;
  const nurseSet = new Set<string>();
  const agencyNurseSet = new Set<string>();

  for (const day of map.values()) {
    for (const shift of day.shifts) {
      totalRequiredHours += shift.requiredHours;
      totalActualHours += shift.actualHours;

      if (!shift.isHPRDMet || shift.nurses.length === 0) {
        openShiftCount++;
      }

      for (const nurse of shift.nurses) {
        nurseSet.add(nurse.id);
        if (nurse.isAgency) {
          agencyNurseSet.add(nurse.id);
          agencyHours += nurse.shiftHours;
        }
      }
    }
  }

  const coveragePct = totalRequiredHours > 0
    ? Math.min(100, Math.max(0, (totalActualHours / totalRequiredHours) * 100))
    : 0;

  const staffMixPct = nurseSet.size > 0
    ? ((nurseSet.size - agencyNurseSet.size) / nurseSet.size) * 100
    : 0;

  return [
    {
      label: "Coverage Score",
      value: `${Math.round(coveragePct)}%`,
      detail: "Target-ready census coverage",
      icon: MODULE_ICONS.scheduling[0],
      tone: coveragePct >= 90 ? "success" : "warning",
    },
    {
      label: "Open Shifts",
      value: `${openShiftCount}`,
      detail: "Needs planner review",
      icon: MODULE_ICONS.scheduling[1],
      tone: openShiftCount > 0 ? "warning" : "success",
    },
    {
      label: "Agency Hours",
      value: `${Math.round(agencyHours)} hrs`,
      detail: "External staff hours booked",
      icon: MODULE_ICONS.scheduling[2],
      tone: agencyHours > 0 ? "warning" : "success",
    },
    {
      label: "Staff Mix",
      value: `${Math.round(staffMixPct)}%`,
      detail: "Internal team utilization",
      icon: MODULE_ICONS.scheduling[3],
      tone: staffMixPct >= 80 ? "success" : "warning",
    },
  ];
}

function computeAnalyzerMetrics(
  financials: { totalEnterpriseCost: number; totalIncentiveCost: number; totalOvertimeCost: number } | null,
  map: ScheduleMap,
  _optSummary: unknown,
): ExecutiveMetric[] {
  void _optSummary;
  let totalActualHours = 0;
  let totalPatientCount = 0;

  for (const day of map.values()) {
    for (const shift of day.shifts) {
      totalActualHours += shift.actualHours;
      totalPatientCount += shift.patientCount;
    }
  }

  const avgHppd = totalPatientCount > 0 ? totalActualHours / totalPatientCount : 0;

  const laborSpend = financials?.totalEnterpriseCost != null
    ? `$${Math.round(financials.totalEnterpriseCost).toLocaleString()}`
    : "--";

  const agencyUtil = financials?.totalEnterpriseCost != null && financials.totalEnterpriseCost > 0
    ? `${((financials.totalIncentiveCost / financials.totalEnterpriseCost) * 100).toFixed(1)}%`
    : "--";

  const overtimeRisk = financials?.totalEnterpriseCost != null && financials.totalEnterpriseCost > 0
    ? `${((financials.totalOvertimeCost / financials.totalEnterpriseCost) * 100).toFixed(1)}%`
    : "--";

  const overtimeRiskNum = financials?.totalEnterpriseCost != null && financials.totalEnterpriseCost > 0
    ? (financials.totalOvertimeCost / financials.totalEnterpriseCost) * 100
    : 0;

  return [
    {
      label: "Labor Spend",
      value: laborSpend,
      detail: "Month-to-date cost baseline",
      icon: MODULE_ICONS.analyzer[0],
      tone: "neutral",
    },
    {
      label: "Agency Utilization",
      value: agencyUtil,
      detail: "Incentive cost as % of total",
      icon: MODULE_ICONS.analyzer[1],
      tone: "neutral",
    },
    {
      label: "Avg HPPD",
      value: avgHppd.toFixed(2),
      detail: "Hours per patient day",
      icon: MODULE_ICONS.analyzer[2],
      tone: "neutral",
    },
    {
      label: "Overtime Risk",
      value: overtimeRisk,
      detail: "Overtime cost as % of total",
      icon: MODULE_ICONS.analyzer[3],
      tone: overtimeRiskNum > 5 ? "warning" : "success",
    },
  ];
}

function computeForecastMetrics(map: ScheduleMap, draftPatchCount: number): ExecutiveMetric[] {
  let weekendHours = 0;
  let weekendPatientCount = 0;
  let totalShifts = 0;
  let compliantShifts = 0;
  const nurseShiftCount = new Map<string, number>();

  for (const [dateStr, day] of map.entries()) {
    const date = new Date(dateStr + "T00:00:00");
    const isWeekend = date.getDay() === 0 || date.getDay() === 6;

    for (const shift of day.shifts) {
      totalShifts++;
      if (shift.isHPRDMet) compliantShifts++;

      if (isWeekend) {
        weekendHours += shift.actualHours;
        weekendPatientCount += shift.patientCount;
      }

      for (const nurse of shift.nurses) {
        nurseShiftCount.set(nurse.id, (nurseShiftCount.get(nurse.id) ?? 0) + 1);
      }
    }
  }

  const weekendHppd = weekendPatientCount > 0 ? weekendHours / weekendPatientCount : 0;
  const burnoutCount = Array.from(nurseShiftCount.values()).filter((count) => count >= 5).length;
  const complianceScore = totalShifts > 0 ? (compliantShifts / totalShifts) * 100 : 0;

  return [
    {
      label: "Weekend HPPD",
      value: weekendHppd.toFixed(2),
      detail: "Weekend hours per patient day (schedule-derived)",
      icon: MODULE_ICONS["ml-forecasts"][0],
      tone: "warning",
    },
    {
      label: "Burnout Flags",
      value: burnoutCount > 0 ? `${burnoutCount} RNs` : "0 RNs",
      detail: "Nurses on 5+ shifts this period (schedule-derived)",
      icon: MODULE_ICONS["ml-forecasts"][1],
      tone: burnoutCount > 0 ? "warning" : "success",
    },
    {
      label: "Compliance Score",
      value: `${Math.round(complianceScore)}%`,
      detail: "Shifts meeting HPRD target (schedule-derived)",
      icon: MODULE_ICONS["ml-forecasts"][2],
      tone: complianceScore > 90 ? "success" : "warning",
    },
    {
      label: "Pending Actions",
      value: draftPatchCount > 0 ? `${draftPatchCount} staged` : "0 staged",
      detail: "Staged patches awaiting run (schedule-derived)",
      icon: MODULE_ICONS["ml-forecasts"][3],
      tone: draftPatchCount > 0 ? "warning" : "neutral",
    },
  ];
}

export function useExecutiveMetrics(activeModule: ModuleOption): {
  metrics: ExecutiveMetric[];
  scheduleCount: number;
} {
  const {
    scheduleCount,
    effectiveScheduleMap,
    optimizationFinancials,
    latestOptimization,
    draftPatchCount,
  } = useSchedulingStore(
    useShallow((state) => ({
      scheduleCount: state.effectiveScheduleMap.size,
      effectiveScheduleMap: state.effectiveScheduleMap,
      optimizationFinancials: state.optimizationFinancials,
      latestOptimization: state.latestOptimization,
      draftPatchCount: state.draftState.patches.length,
    })),
  );

  const metrics = useMemo(() => {
    if (scheduleCount === 0) {
      return getEmptyMetrics(activeModule);
    }

    switch (activeModule) {
      case "scheduling":
        return computeSchedulingMetrics(effectiveScheduleMap);
      case "analyzer":
        return computeAnalyzerMetrics(optimizationFinancials, effectiveScheduleMap, latestOptimization);
      case "ml-forecasts":
        return computeForecastMetrics(effectiveScheduleMap, draftPatchCount);
      default:
        return getEmptyMetrics(activeModule);
    }
  }, [activeModule, effectiveScheduleMap, optimizationFinancials, latestOptimization, draftPatchCount, scheduleCount]);

  return { metrics, scheduleCount };
}
