from dataclasses import dataclass
from typing import Dict, List

import pendulum

from snf_schedule_optimizer.data_models import NurseProfile, Shift
from snf_schedule_optimizer.overtime_calculation import IOvertimeCalculator


@dataclass(frozen=True)
class NurseShiftHourComponent:
    shift: Shift
    start_time: pendulum.DateTime
    end_time: pendulum.DateTime
    is_ot: bool

    @property
    def duration_hours(self) -> float:
        return (self.end_time - self.start_time).total_hours()


class NurseShiftHoursStateTracker:

    def __init__(
            self,
            nurse_profile: NurseProfile,
            overtime_calculator: IOvertimeCalculator,
    ):
        self.nurse_profile = nurse_profile
        self.nurse_shift_history: Dict[Shift, List[NurseShiftHourComponent]] = {}
        self.overtime_calculator = overtime_calculator

    def record_shift_and_get_hour_components(self, shift: Shift) -> List[NurseShiftHourComponent]:
        if shift in self.nurse_shift_history:
            return self.nurse_shift_history[shift]

        self.nurse_shift_history[shift] = []
        remaining_non_ot_hours = self.overtime_calculator.get_remaining_non_ot_hours(
            nurse_profile=self.nurse_profile,
            current_shift=shift,
            nurse_shift_history=self.nurse_shift_history,
        )

        if remaining_non_ot_hours <= 0:
            # Entire shift is OT
            hour_component = NurseShiftHourComponent(
                shift=shift,
                start_time=shift.shift_start_time,
                end_time=shift.shift_end_time,
                is_ot=True
            )
            self.nurse_shift_history[shift].append(
                hour_component
            )
            return [hour_component]

        if shift.duration_hours <= remaining_non_ot_hours:
            # Entire shift is regular time
            component = NurseShiftHourComponent(
                shift=shift,
                start_time=shift.shift_start_time,
                end_time=shift.shift_end_time,
                is_ot=False
            )
            self.nurse_shift_history[shift].append(
                component
            )
            return [component]

        remaining_non_ot_duration = pendulum.Duration(hours=remaining_non_ot_hours)

        components = []

        # Split shift into regular time and OT
        regular_end_time = shift.shift_start_time + remaining_non_ot_duration

        components.append(
            NurseShiftHourComponent(
                shift=shift,
                start_time=shift.shift_start_time,
                end_time=regular_end_time,
                is_ot=False
            )
        )

        components.append(
            NurseShiftHourComponent(
                shift=shift,
                start_time=regular_end_time,
                end_time=shift.shift_end_time,
                is_ot=True
            )
        )

        self.nurse_shift_history[shift].extend(components)

        return components

    def _get_shifts_before(self, current_shift: Shift) -> List[NurseShiftHourComponent]:
        """Get all shift components before the current shift's start time."""
        shifts_before = []
        for shift, components in self.nurse_shift_history.items():
            if shift.shift_start_time < current_shift.shift_start_time:
                shifts_before.extend(components)
            else:
                break
        return shifts_before

    def _calculate_all_shifts_total_hours(self) -> float:
        """Calculate total hours worked in the last N days before current shift."""
        total_hours = 0.0

        for shift, components in self.nurse_shift_history.items():
            total_hours += shift.duration_hours

        return total_hours
