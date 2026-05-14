import pulp

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    LockedAssignment,
    Schedule,
    ShiftKey,
)
from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder
from snf_schedule_optimizer.optimizer.interfaces import (
    IFacilityScopedConstraintStrategy,
    IScenarioDataProvider,
)
from snf_schedule_optimizer.optimizer.lp_helpers import build_lp_variable_name
from snf_schedule_optimizer.optimizer.models import InfeasibilityReasonResult


class PinnedScheduleConstraintStrategy(IFacilityScopedConstraintStrategy):
    """
    Forces the solver to adhere strictly to a pre-defined schedule.
    Used for validation: if the solver finds this 'Infeasible', the schedule violates constraints.
    """

    def __init__(self, target_schedule: Schedule):
        self.target_schedule = target_schedule

    async def apply_constraints(
        self,
        problem: pulp.LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        # 1. Get all variables relevant to this facility
        # (The holder keys are (facility_id, employee_id, shift_id))
        all_vars = lp_holder.get_all_assignments()

        for shift_key, lp_var in all_vars.items():
            # Only constrain variables for this facility context
            if shift_key.shift.facility_id != facility_id:
                continue

            # 2. Check if this assignment exists in the target schedule
            # shift_assignments is Dict[shift_id, List[employee_id]]
            assigned_employees = self.target_schedule.shift_assignments.get(
                ShiftKey(shift_key.shift.facility_id, shift_key.shift.shift_id),
                [],
            )

            is_assigned = shift_key.employee_id in assigned_employees

            if is_assigned:
                # Force variable to 1 (Must Work)
                problem += (
                    lp_var == 1,
                    build_lp_variable_name(
                        "Pin_Assigned",
                        shift_key.shift.facility_id,
                        str(shift_key.employee_id),
                        shift_key.shift.shift_id,
                    ),
                )
            else:
                # Force variable to 0 (Must Not Work)
                problem += (
                    lp_var == 0,
                    build_lp_variable_name(
                        "Pin_Unassigned",
                        shift_key.shift.facility_id,
                        str(shift_key.employee_id),
                        shift_key.shift.shift_id,
                    ),
                )

        return None


class LockedAssignmentConstraintStrategy(IFacilityScopedConstraintStrategy):
    """Forces selected future assignments without freezing the rest of the schedule."""

    def __init__(self, locked_assignments: list[LockedAssignment]):
        self.locked_assignments = tuple(locked_assignments)

    async def apply_constraints(
        self,
        problem: pulp.LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        shifts_by_key = {
            ShiftKey(shift.facility_id, shift.shift_id): shift
            for shift in data_provider.get_shifts_for_facility(facility_id)
        }

        for locked in self.locked_assignments:
            if locked.shift_key.facility_id != facility_id:
                continue

            shift = shifts_by_key.get(locked.shift_key)
            if shift is None:
                continue

            lp_var = lp_holder.get_variable(shift, locked.employee_id)
            if lp_var is None:
                continue

            problem += (
                lp_var == 1,
                build_lp_variable_name(
                    "LockedAssignment",
                    facility_id,
                    locked.employee_id,
                    shift.shift_id,
                ),
            )

        return None
