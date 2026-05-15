from snf_schedule_optimizer.domain.hr.interfaces import IStaffCompensationRepo
from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IPreferencePenaltyProcessor,
)
from snf_schedule_optimizer.models import (
    Employee,
    NurseProfile,
    PreferenceType,
    PreferenceWeights,
    Shift,
)


class PreferencePenaltyProcessorImpl(IPreferencePenaltyProcessor):
    def __init__(
        self,
        staff_compensation_retriever: IStaffCompensationRepo,
    ):
        self.staff_compensation_retriever = staff_compensation_retriever

    async def calculate_penalty_cost(
        self,
        employee: Employee,
        nurse: NurseProfile,
        shift: Shift,
        preference_weights: PreferenceWeights,
        accumulated_hours: float = 0.0,
    ) -> float:
        """
        Calculates the non-financial penalty cost if the assignment violates a soft preference.
        This cost is added to the LP objective function.
        """
        penalty = 0.0

        # Penalize assigning a nurse to a night shift if they prefer days
        if not shift.day_shift:
            if nurse.shift_custom_preferences and any(
                p
                for p in nurse.shift_custom_preferences
                if p.preference_type.DAY_SHIFT_PREFERENCE
            ):
                # The 'weights' parameter controls the impact of this penalty on the solver
                penalty += preference_weights.custom_preference_penalty

        if shift.day_shift:
            if nurse.shift_custom_preferences and any(
                p
                for p in nurse.shift_custom_preferences
                if p.preference_type.NIGHT_SHIFT_PREFERENCE
            ):
                penalty += preference_weights.custom_preference_penalty

        if nurse.shift_custom_preferences is not None:
            for p in nurse.shift_custom_preferences:
                if p.preference_type == PreferenceType.SPECIFIC_DAY_OFF:
                    try:
                        preference_day_int = (
                            int(p.specific_value)
                            if p.specific_value is not None
                            else -1
                        )
                        if shift.day_of_week.value == preference_day_int:
                            penalty += preference_weights.custom_preference_penalty
                            break
                    except ValueError:
                        # Ignore invalid preference values
                        pass

        if self._is_overtime_risk(nurse, shift, accumulated_hours):
            comp_record = await self.staff_compensation_retriever.get_record_for_date(
                shift.org_id,
                employee.employee_id,
                shift.shift_start_dt.start_of_day().date(),
            )
            if comp_record is not None:
                penalty += (
                    preference_weights.ot_avoidance_penalty
                    * comp_record.base_rate_effective
                )

        return penalty

    @staticmethod
    def _is_overtime_risk(
        nurse: NurseProfile,
        shift: Shift,
        accumulated_hours: float,
    ) -> bool:
        projected = accumulated_hours + shift.duration_hours
        return projected > nurse.available_hours_weekly
