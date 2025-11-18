import abc
from typing import Dict, List

import pendulum

from snf_schedule_optimizer.data_models import FacilityConfig, NurseProfile, NurseShiftHourComponent, Shift


class IOvertimeCalculator(abc.ABC):
    @abc.abstractmethod
    def get_remaining_non_ot_hours(
            self,
            nurse_profile: NurseProfile,
            current_shift: Shift,
            nurse_shift_history: Dict[Shift, List[NurseShiftHourComponent]],
    ) -> float:
        pass


class BasicOvertimeCalculator(IOvertimeCalculator):
    def __init__(
            self,
            facility_config: FacilityConfig,
    ):
        self.overtime_threshold_hours_per_week = facility_config.overtime_threshold_hours_per_week
        self.start_of_work_week_day = facility_config.start_of_work_week_day
        self.start_of_work_day_time = facility_config.start_of_work_day_time

    def get_remaining_non_ot_hours(
            self,
            nurse_profile: NurseProfile,
            current_shift: Shift,
            nurse_shift_history: Dict[Shift, List[NurseShiftHourComponent]],
    ) -> float:
        total_hours_worked = 0.0

        beginning_of_work_week_dt = current_shift.shift_start_dt.start_of('week').add(
            days=self.start_of_work_week_day - pendulum.WeekDay.MONDAY,
            hours=self.start_of_work_day_time.hour,
            minutes=self.start_of_work_day_time.minute,
            seconds=self.start_of_work_day_time.second,
        )

        for shift, components in nurse_shift_history.items():
            if beginning_of_work_week_dt <= shift.shift_end_dt <= current_shift.shift_start_dt:
                for component in components:
                    if component.start_time >= beginning_of_work_week_dt:
                        total_hours_worked += component.duration_hours

        remaining_non_ot_hours = max(
            0.0,
            self.overtime_threshold_hours_per_week - total_hours_worked
        )

        return remaining_non_ot_hours
