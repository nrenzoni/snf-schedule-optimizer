import pulp
from pulp import LpProblem

from snf_schedule_optimizer.models import DomainPrimaryKeyType
from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder
from snf_schedule_optimizer.optimizer.interfaces import (
    IFacilityScopedConstraintStrategy,
    INurseHardBlockChecker,
    IScenarioDataProvider,
)
from snf_schedule_optimizer.optimizer.lp_helpers import build_lp_variable_name
from snf_schedule_optimizer.optimizer.models import (
    InfeasibilityReason,
    InfeasibilityReasonResult,
)


class HprdStaffingConstraintStrategy(IFacilityScopedConstraintStrategy):
    def __init__(
        self,
        hard_block_checker: INurseHardBlockChecker,
    ):
        self.hard_block_checker = hard_block_checker

    async def apply_constraints(
        self,
        problem: pulp.LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        # todo: Add infeasibility checks (e.g., no available nurses for a required role)

        requirements_holder = await data_provider.get_hprd_requirements_for_facility(
            facility_id
        )
        shifts = data_provider.get_shifts_for_facility(facility_id)

        # "For every shift, sum of assigned nurses >= Required HPRD count"
        for shift in shifts:
            # Get requirements (e.g., {RN: 2.5, CNA: 10.0})
            # This assumes your HPRD holder logic is accessible or pre-calculated
            # For simplicity, let's assume we iterate roles:
            for role in requirements_holder.roles:
                required_count = requirements_holder[shift.shift_id, role]

                if required_count <= 0:
                    continue

                available_vars = []
                nurses = await data_provider.get_nurses_for_shift(shift)

                for nurse in nurses:
                    # Filter by Hard Blocks (Time off, etc.)
                    # Note: We enforce blocks by NOT adding the variable to the sum,
                    # OR by explicitly adding x = 0 constraint.
                    # Explicit constraint is safer for transparency.
                    lp_var = lp_holder.get_variable(
                        shift,
                        nurse.employee_id,
                    )

                    if lp_var is None:
                        continue

                    if self.hard_block_checker.check(nurse, shift):
                        # HARD BLOCK: Force variable to 0
                        problem += (
                            lp_var == 0,
                            build_lp_variable_name(
                                "HardBlock", nurse.employee_id, shift.shift_id
                            ),
                        )
                        continue

                    # Filter by Role
                    employee = await data_provider.get_employee_by_id(nurse.employee_id)
                    if not employee:
                        continue  # todo: should this be an error?

                    if employee.job_title != role.value:
                        continue

                    # Available: Add to the pool
                    available_vars.append(lp_var)

                if len(available_vars) == 0:
                    return InfeasibilityReasonResult(
                        reason=InfeasibilityReason.NO_AVAILABLE_NURSES,
                        details=f"No available nurses for role {role.value} in shift {shift.shift_id} at facility {facility_id}.",
                    )

                # Add the HPRD Sum Constraint
                problem += (
                    pulp.lpSum(available_vars) >= required_count,
                    build_lp_variable_name(
                        "MinStaff", shift.facility_id, shift.shift_id, role.value
                    ),
                )

            total_required = requirements_holder.get_total_req(shift.shift_id)
            if total_required <= 0:
                continue

            total_available_vars = []
            for nurse in await data_provider.get_nurses_for_shift(shift):
                lp_var = lp_holder.get_variable(shift, nurse.employee_id)
                if lp_var is None or self.hard_block_checker.check(nurse, shift):
                    continue
                employee = await data_provider.get_employee_by_id(nurse.employee_id)
                if employee is None:
                    continue
                if employee.job_title in {role.value for role in requirements_holder.roles}:
                    total_available_vars.append(lp_var)

            if len(total_available_vars) == 0:
                return InfeasibilityReasonResult(
                    reason=InfeasibilityReason.NO_AVAILABLE_NURSES,
                    details=f"No available direct-care nurses in shift {shift.shift_id} at facility {facility_id}.",
                )

            problem += (
                pulp.lpSum(total_available_vars) >= total_required,
                build_lp_variable_name("MinStaffTotal", shift.facility_id, shift.shift_id),
            )

        return None


class ConsecutiveShiftFatigueStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        shifts = sorted(
            data_provider.get_shifts_for_facility(facility_id),
            key=lambda shift: shift.shift_start_dt,
        )
        min_rest_hours = data_provider.get_optimization_settings().min_rest_period

        for i in range(len(shifts) - 1):
            for j in range(i + 1, len(shifts)):
                s1, s2 = shifts[i], shifts[j]
                if s2.shift_start_dt <= s1.shift_start_dt:
                    continue
                gap = (s2.shift_start_dt - s1.shift_end_dt).in_hours()
                if gap >= min_rest_hours:
                    break

                nurses_s1 = {
                    n.employee_id for n in await data_provider.get_nurses_for_shift(s1)
                }
                nurses_s2 = {
                    n.employee_id for n in await data_provider.get_nurses_for_shift(s2)
                }
                common = nurses_s1.intersection(nurses_s2)

                for emp_id in common:
                    v1 = lp_holder.get_variable(s1, emp_id)
                    v2 = lp_holder.get_variable(s2, emp_id)
                    if v1 is None or v2 is None:
                        continue
                    problem += (
                        v1 + v2 <= 1,
                        f"Fatigue_{facility_id}_{emp_id}_{s1.shift_id}_{s2.shift_id}",
                    )

        return None


class MaxShiftLengthConstraintStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        max_shift_length = data_provider.get_optimization_settings().max_shift_length
        for shift in data_provider.get_shifts_for_facility(facility_id):
            if shift.duration_hours <= max_shift_length:
                continue

            for nurse in await data_provider.get_nurses_for_shift(shift):
                lp_var = lp_holder.get_variable(shift, nurse.employee_id)
                if lp_var is None:
                    continue
                problem += (
                    lp_var == 0,
                    build_lp_variable_name(
                        "MaxShiftLength",
                        facility_id,
                        shift.shift_id,
                        nurse.employee_id,
                    ),
                )
        return None
