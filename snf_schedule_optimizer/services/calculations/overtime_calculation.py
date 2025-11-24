import abc
from dataclasses import dataclass
from typing import Dict, List, Optional

import pendulum

from snf_schedule_optimizer.models import Employee, OvertimeInterval, OvertimeTrigger, WorkedShiftSegment, Shift
from snf_schedule_optimizer.models.constraints import LookbackPeriod
from snf_schedule_optimizer.services.interfaces import IEmployeeWorkHistoryService, IOvertimeCalculator, IOvertimeRule


class ThresholdOvertimeRule(IOvertimeRule):
    """
    Implements a pay rule based on hours worked threshold (daily or weekly).


    This rule is the source of truth for a specific OT type (e.g., 'CA State OT' or 'Union Local 123 OT').


    This class is purely the definition/metadata source.
    """

    def __init__(
            self,
            name: str,
            multiplier: float,
            trigger: OvertimeTrigger,
            priority: int,  # Higher number means checked first if conflicts exist
            applicable_job_titles: Optional[List[str]] = None,
            required_certificates: Optional[List[str]] = None,
    ):
        self.name = name
        self._multiplier = multiplier
        self.trigger = trigger
        self._priority = priority
        self._applicable_job_titles = applicable_job_titles
        self.required_certificates = required_certificates

    @property
    def multiplier(self) -> float:
        """Returns the multiplier required by this rule (e.g., 1.5)."""
        return self._multiplier

    @property
    def priority(self) -> int:
        """Returns the priority of this rule for conflict resolution."""
        return self._priority

    @property
    def applicable_job_titles(self) -> Optional[List[str]]:
        return self._applicable_job_titles


class OvertimeCalculatorImpl(IOvertimeCalculator):

    def __init__(
            self,
            work_history_service: IEmployeeWorkHistoryService,
    ):
        self.work_history_service = work_history_service

    def get_overtime_intervals(
            self,
            shift: Shift,
            employee: Employee,
            work_shift_history: Dict[Shift, List[WorkedShiftSegment]],
            overtime_rules: List['IOvertimeRule'],
    ) -> List[OvertimeInterval]:
        """
        Calculates all overlapping and sequential overtime intervals for the current shift,
        assigning all triggering rules to each segment.
        """

        threshold_rules: List[ThresholdOvertimeRule] = []
        for rule in overtime_rules:
            if isinstance(rule, ThresholdOvertimeRule):
                threshold_rules.append(rule)
            else:
                # Log non-threshold rules, as they shouldn't be passed here if filtering is correct
                print(f"WARNING: Non-threshold rule passed to OT calculator: {type(rule).__name__}")

        if not threshold_rules:
            return []

            # Calculate the required remaining non-OT hours for all rules
        remaining_non_ot = self.work_history_service.get_remaining_non_ot_hours(employee, shift, threshold_rules)

        # Collect All Boundary Events (Start/End points)
        # We need a sorted list of all unique time points where OT status changes.
        # Initial points: shift start and end.
        boundary_times = {shift.shift_start_dt, shift.shift_end_dt}

        # Map: Rule -> OT Start Time
        rule_ot_start_map: Dict[IOvertimeRule, pendulum.DateTime] = {}

        # --- 1. Process Threshold and Tiered Rules (Daily/Weekly) ---

        # --- Daily/Weekly Thresholds ---
        for rule in threshold_rules:
            trigger = rule.trigger

            # Determine the effective threshold (Daily or Weekly)
            if trigger.daily_threshold is not None:
                remaining = remaining_non_ot[LookbackPeriod.DAILY]
            elif trigger.weekly_threshold is not None:
                remaining = remaining_non_ot[LookbackPeriod.WEEKLY]
            else:
                # Skip rules with no daily/weekly threshold defined (e.g., only consecutive day rule)
                continue

            ot_start_time = self._get_ot_trigger_time(shift, remaining)

            # OT must start within the shift's boundaries
            if shift.shift_start_dt < ot_start_time < shift.shift_end_dt:
                boundary_times.add(ot_start_time)
                rule_ot_start_map[rule] = ot_start_time
            elif ot_start_time <= shift.shift_start_dt:
                # If OT started before the shift, the entire shift is OT
                rule_ot_start_map[rule] = shift.shift_start_dt

        # --- 2. Process Calendar/Consecutive Rules ---

        # --- Consecutive Day Trigger ---

        consecutive_thresholds = [
            r.trigger.consecutive_day_threshold
            for r in threshold_rules
            if r.trigger.consecutive_day_threshold is not None
        ]
        max_days = max(consecutive_thresholds) if consecutive_thresholds else 0
        if max_days > 0:
            consecutive_days_worked = self.work_history_service.get_consecutive_days_worked(
                employee,
                shift,
                work_shift_history,
                max_days
            )
            if len(consecutive_days_worked) >= max_days:
                # If the employee is working the Nth consecutive day, the entire shift is OT
                for rule in threshold_rules:
                    if rule.trigger.consecutive_day_threshold == max_days:
                        rule_ot_start_map[rule] = shift.shift_start_dt

        # Sort Boundaries and Create Segments
        sorted_boundaries = sorted(boundary_times)
        final_intervals: List[OvertimeInterval] = []

        for i in range(len(sorted_boundaries) - 1):
            interval_start = sorted_boundaries[i]
            interval_end = sorted_boundaries[i + 1]

            # if interval_start >= interval_end:
            #     continue

            # Check the midpoint of the segment to see which rules apply
            midpoint = interval_start.add(seconds=(interval_end - interval_start).total_seconds() / 2)

            segment_rules: List[IOvertimeRule] = []

            # Determine all rules active during this segment
            for rule, ot_start_dt in rule_ot_start_map.items():
                if midpoint >= ot_start_dt:
                    # The rule applies from its calculated OT start time onward
                    segment_rules.append(rule)

            # Only create an interval if the segment is actually OT (rules apply)
            if segment_rules:
                final_intervals.append(
                    OvertimeInterval(
                        start_dt=interval_start,
                        end_dt=interval_end,
                        applicable_rules=segment_rules,
                    )
                )

        return final_intervals

    def _get_ot_trigger_time(self, shift: 'Shift', remaining_hours: float) -> pendulum.DateTime:
        """Calculates the exact DateTime when OT starts on the current shift."""
        if remaining_hours <= 0:
            return shift.shift_start_dt

        duration_delta = pendulum.duration(hours=remaining_hours)

        # OT starts only after the remaining non-OT hours are worked
        return shift.shift_start_dt + duration_delta

    # def get_overtime_intervals(
    #         self, shift: Shift, employee: Employee,
    # ) -> List[OvertimeInterval]:
    #     # This is where the complex state/union threshold logic lives.
    #
    #     # Placeholder: Assume OT starts 4 hours into the shift for 1.5x
    #     # todo: replace overtime multiplier with audit-compliant records
    #     ot_start = shift.shift_start_dt.add(hours=4)
    #     if ot_start < shift.shift_end_dt:
    #         # Ensure the multiplier is "most favorable"
    #         return [
    #             OvertimeInterval(
    #                 start_dt=ot_start,
    #                 end_dt=shift.shift_end_dt,
    #                 multiplier=1.5
    #             )
    #         ]
    #     return []

    # def get_remaining_non_ot_hours(
    #         self,
    #         nurse_profile: NurseProfile,
    #         current_shift: Shift,
    #         nurse_shift_history: Dict[Shift, List[WorkedShiftSegment]],
    # ) -> float:
    #     total_hours_worked = 0.0
    #
    #     beginning_of_work_week_dt = current_shift.shift_start_dt.start_of('week').add(
    #         days=self.start_of_work_week_day - pendulum.WeekDay.MONDAY,
    #         hours=self.start_of_work_day_time.hour,
    #         minutes=self.start_of_work_day_time.minute,
    #         seconds=self.start_of_work_day_time.second,
    #     )
    #
    #     for shift, components in nurse_shift_history.items():
    #         if beginning_of_work_week_dt <= shift.shift_end_dt <= current_shift.shift_start_dt:
    #             for component in components:
    #                 if component.start_time >= beginning_of_work_week_dt:
    #                     total_hours_worked += component.duration_hours
    #
    #     remaining_non_ot_hours = max(
    #         0.0,
    #         self.overtime_threshold_hours_per_week - total_hours_worked
    #     )
    #
    #     return remaining_non_ot_hours

    # def calculate_overtime_intervals(
    #         self,
    #         nurse_profile: NurseProfile,
    #         current_shift: Shift,
    #         nurse_shift_history: Dict[Shift, List[WorkedShiftSegment]],
    # ) -> List[pendulum.Interval]:
    #     pass
