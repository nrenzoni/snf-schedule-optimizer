from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider


class CoreVariableGenerationStrategy:
    """Defines the fundamental decision variables (Nurse X assigned to Shift Y)."""

    def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: str,
    ) -> None:
        shifts = data_provider.get_shifts_for_facility(facility_id)
        for shift in shifts:
            # Use the provider!
            nurses = data_provider.get_nurses_for_shift(shift)
            for nurse in nurses:
                lp_holder.add_variable(nurse.employee_id, shift.shift_id)
