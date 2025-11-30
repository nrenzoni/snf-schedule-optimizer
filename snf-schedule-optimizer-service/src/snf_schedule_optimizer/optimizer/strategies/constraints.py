from typing import Optional

import pulp
from pulp import LpProblem

from snf_schedule_optimizer.models import HprdEnforcedRole
from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder
from snf_schedule_optimizer.optimizer.interfaces import (
    IFacilityScopedConstraintStrategy,
    INurseHardBlockChecker,
    IScenarioDataProvider,
)
from snf_schedule_optimizer.optimizer.models import InfeasibilityReasonResult


class HprdStaffingConstraintStrategy(IFacilityScopedConstraintStrategy):
    def __init__(
        self,
        hard_block_checker: INurseHardBlockChecker,
    ):
        self.hard_block_checker = hard_block_checker

    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
        facility_id: str,
    ) -> Optional[InfeasibilityReasonResult]:
        # todo: Add infeasibility checks (e.g., no available nurses for a required role)

        requirements_holder = data_provider.get_hprd_requirements_for_facility(
            facility_id
        )
        shifts = data_provider.get_shifts_for_facility(facility_id)

        # "For every shift, sum of assigned nurses >= Required HPRD count"
        for shift in shifts:
            # Get requirements (e.g., {RN: 2.5, CNA: 10.0})
            # This assumes your HPRD holder logic is accessible or pre-calculated
            # For simplicity, let's assume we iterate roles:
            for role in [HprdEnforcedRole.RN, HprdEnforcedRole.CNA]:
                required_count = requirements_holder[shift.shift_id, role]

                if required_count <= 0:
                    continue

                available_vars = []
                nurses = data_provider.get_nurses_for_shift(shift)

                for nurse in nurses:
                    # Filter by Hard Blocks (Time off, etc.)
                    # Note: We enforce blocks by NOT adding the variable to the sum,
                    # OR by explicitly adding x = 0 constraint.
                    # Explicit constraint is safer for transparency.
                    lp_var = lp_holder.get_variable(nurse.employee_id, shift.shift_id)

                    if self.hard_block_checker.check(nurse, shift):
                        # HARD BLOCK: Force variable to 0
                        problem += (
                            lp_var == 0,
                            f"HardBlock_{nurse.employee_id}_{shift.shift_id}",
                        )
                        continue

                    # Filter by Role
                    employee = data_provider.get_employee_by_id(nurse.employee_id)
                    if not employee:
                        continue  # todo: should this be an error?

                    if employee.job_title != role.value:
                        continue

                    # Available: Add to the pool
                    available_vars.append(lp_var)

                # Add the HPRD Sum Constraint
                problem += (
                    pulp.lpSum(available_vars) >= required_count,
                    f"MinStaff_{shift.shift_id}_{role.value}",
                )

        return None


class ConsecutiveShiftFatigueStrategy(IFacilityScopedConstraintStrategy):
    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
        facility_id: str,
    ) -> Optional[InfeasibilityReasonResult]:
        shifts = data_provider.get_all_shifts()

        # todo: Make this more generic/configurable, add infeasibility checks

        # Simple example: Cannot work Shift 1 AND Shift 2 if they overlap or are back-to-back
        # (You can inject a specific logic class here if it gets complex)
        for i in range(len(shifts) - 1):
            s1, s2 = shifts[i], shifts[i + 1]
            # Simple check: if < 8 hours gap
            gap = (s2.shift_start_dt - s1.shift_end_dt).total_hours()
            if gap < 8.0:
                # Find common nurses
                nurses_s1 = {
                    n.employee_id for n in data_provider.get_nurses_for_shift(s1)
                }
                nurses_s2 = {
                    n.employee_id for n in data_provider.get_nurses_for_shift(s2)
                }
                common = nurses_s1.intersection(nurses_s2)

                for emp_id in common:
                    v1 = lp_holder.get_variable(emp_id, s1.shift_id)
                    v2 = lp_holder.get_variable(emp_id, s2.shift_id)
                    problem += v1 + v2 <= 1, f"Fatigue_{emp_id}_{s1.shift_id}"

        return None
