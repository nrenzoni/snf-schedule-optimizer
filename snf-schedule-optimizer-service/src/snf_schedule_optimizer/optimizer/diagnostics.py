from collections import defaultdict
from dataclasses import dataclass

from snf_schedule_optimizer.models import DomainPrimaryKeyType, HprdEnforcedRole
from snf_schedule_optimizer.optimizer.calculators import NurseHardBlockCheckerImpl
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider


@dataclass(frozen=True)
class ShiftBottleneck:
    shift_id: DomainPrimaryKeyType
    time_label: str
    role: str
    required_count: float
    available_count: int
    blocked_count: int


class SchedulerInfeasibilityDiagnoser:
    """
    Analyzes the input data when an optimization fails to identify likely causes.
    Performs heuristic checks on Supply vs Demand constraints.
    """

    def __init__(self, data_provider: IScenarioDataProvider):
        self.provider = data_provider
        # We instantiate a checker directly to test static constraints (preferences, skills)
        self.block_checker = NurseHardBlockCheckerImpl()

    async def generate_report_string(self) -> str:
        """Returns a formatted string report of potential infeasibility causes."""
        report: list[str] = [
            "\n" + "!" * 60,
            "INFEASIBILITY DIAGNOSTICS REPORT",
            "!" * 60,
        ]

        fac_ids = self.provider.get_facility_ids()

        for fac_id in fac_ids:
            report.append(f"\n[Facility: {fac_id}]")

            # 1. Global Capacity Analysis
            report.extend(await self._analyze_global_capacity(fac_id))

            # 2. Shift-Level Bottle Neck Analysis
            report.extend(await self._analyze_shift_bottlenecks(fac_id))

        return "\n".join(report)

    async def _analyze_global_capacity(
        self, facility_id: DomainPrimaryKeyType
    ) -> list[str]:
        output = []
        shifts = self.provider.get_shifts_for_facility(facility_id)
        reqs = await self.provider.get_hprd_requirements_for_facility(facility_id)

        total_req_hours: dict[HprdEnforcedRole, float] = dict.fromkeys(
            HprdEnforcedRole, 0.0
        )

        # Calculate Total Demand (Hours)
        for shift in shifts:
            duration = shift.duration_hours
            for role in [HprdEnforcedRole.RN, HprdEnforcedRole.CNA]:
                # reqs[shift, role] is the headcount required.
                count = reqs[shift.shift_id, role]
                total_req_hours[role] += count * duration

        # Calculate Total Theoretical Supply (Hours)
        # We sum up every employee's potential hours.
        # Note: This assumes employees in the context are available for this facility.
        employees = await self.provider.get_all_employees()
        total_supply_hours: dict[HprdEnforcedRole, float] = dict.fromkeys(
            HprdEnforcedRole, 0.0
        )

        for emp in employees:
            if role2 := self._map_job_to_role(emp.job_title):
                # Heuristic: Assume ~40h available per employee per week
                # A more advanced check would look at NurseProfile.available_hours
                total_supply_hours[role2] += 40.0

        output.append("  Global Supply vs Demand (Heuristic - Weekly):")
        for role in HprdEnforcedRole:
            demand = total_req_hours.get(role, 0)
            supply = total_supply_hours.get(role, 0)
            gap = supply - demand

            if demand > 0:
                status = "OK" if gap >= 0 else "CRITICAL SHORTAGE"
                output.append(
                    f"    {role.value:<5}: Req {demand:6.1f} hrs | Avail ~{supply:6.1f} hrs | Gap {gap:6.1f} ({status})"
                )

        return output

    async def _analyze_shift_bottlenecks(
        self, facility_id: DomainPrimaryKeyType
    ) -> list[str]:
        output = []
        shifts = self.provider.get_shifts_for_facility(facility_id)
        reqs = await self.provider.get_hprd_requirements_for_facility(facility_id)

        output.append("\n  Shift Bottleneck Analysis (Hard Constraints):")

        issues_found = False

        # Sort by time for readability
        for shift in sorted(shifts, key=lambda s: s.shift_start_dt):
            nurses = await self.provider.get_nurses_for_shift(shift)

            # Bucket available nurses by role for THIS specific shift
            available_by_role: dict[HprdEnforcedRole, int] = defaultdict(int)
            blocked_by_role: dict[HprdEnforcedRole, int] = defaultdict(int)

            for nurse in nurses:
                emp = await self.provider.get_employee_by_id(nurse.employee_id)
                if not emp:
                    continue

                role = self._map_job_to_role(emp.job_title)
                if not role:
                    continue

                # Check Static Blocks (e.g. Day Off Preference as Hard Block)
                if self.block_checker.check(nurse, shift):
                    blocked_by_role[role] += 1
                else:
                    available_by_role[role] += 1

            # Check vs Requirements
            for role in HprdEnforcedRole:
                required = reqs[shift.shift_id, role]
                # Use small epsilon for float comparison
                if required < 0.01:
                    continue

                available = available_by_role[role]

                if available < required:
                    issues_found = True
                    time_str = shift.shift_start_dt.format_iso()
                    output.append(f"    [CRITICAL] {shift.shift_id} ({time_str})")
                    output.append(
                        f"      Role {role.value}: Need {required:.1f}, Have {available}"
                    )
                    if blocked_by_role[role] > 0:
                        output.append(
                            f"      (Note: {blocked_by_role[role]} candidates were excluded by Hard Block preferences)"
                        )

        if not issues_found:
            output.append("    No obvious static shift-level coverage gaps found.")
            output.append(
                "    (Infeasibility likely due to dynamic constraints like OT limits or Fatigue rules)"
            )

        return output

    def _map_job_to_role(self, job_title: str) -> HprdEnforcedRole | None:
        """Maps specific job titles (RN_Supervisor) to generic HPRD roles (RN)."""
        jt = job_title.upper()
        if "RN" in jt:
            return HprdEnforcedRole.RN
        if "CNA" in jt:
            return HprdEnforcedRole.CNA
        # LPN logic can be added here
        return None
