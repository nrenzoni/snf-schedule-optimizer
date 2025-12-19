from snf_schedule_optimizer.models import (
    Employee,
    NurseProfile,
    PreferenceType,
    PreferenceWeights,
    Shift,
)
from snf_schedule_optimizer.services.hr.interfaces import IStaffCompensationService
from snf_schedule_optimizer.services.scheduling.interfaces import (
    IPreferencePenaltyProcessor,
)


class PreferencePenaltyProcessorImpl(IPreferencePenaltyProcessor):
    def __init__(
        self,
        staff_compensation_service: IStaffCompensationService,
    ):
        self.staff_compensation_service = staff_compensation_service

    async def calculate_penalty_cost(
        self,
        employee: Employee,
        nurse: NurseProfile,
        shift: Shift,
        preference_weights: PreferenceWeights,
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
            preference_day_string: str | None
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

        # FIX: The ot_multiplier is not on NurseProfile. Delegate the multiplier check
        # to the ShiftPayProcessor or assume a standard rate for soft penalty calculation.
        # Here, we assume the base_rate is enough proxy cost.
        comp_record = await self.staff_compensation_service.get_record_for_date(
            employee.employee_id, shift.shift_start_dt
        )
        if comp_record is None:
            raise ValueError(
                f"Missing compensation record for {employee.employee_id=}, {shift.shift_start_dt=}"
            )
        if self._is_overtime_risk(nurse, shift.day_shift):
            # Use nurse.base_rate (which is on NurseProfile now) as a proxy for cost
            penalty += (
                preference_weights.ot_avoidance_penalty
                * comp_record.base_rate_effective
            )

        # Future implementation: Incorporate penalties for breaking team consistency here
        #

        return penalty

    @staticmethod
    def _is_overtime_risk(nurse: NurseProfile, day_shift: int) -> bool:
        """
        Predictive check: Determines if assigning this shift will push the nurse into OT.
        This logic is complex and requires knowledge of past scheduled shifts.
        """
        # Placeholder: In a real system, this would query scheduled hours from the DB.
        # For this structure, we assume an abstract complexity check.
        # if nurse.scheduled_hours_to_date > 32 and nurse.role != 'Agency':
        #     return True
        return False
