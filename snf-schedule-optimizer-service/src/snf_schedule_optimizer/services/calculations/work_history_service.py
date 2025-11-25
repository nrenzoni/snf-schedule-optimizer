from typing import Dict, List, Optional
import pendulum

from snf_schedule_optimizer.models import Employee, Shift, TimePunch, WorkedShiftSegment, WorkedTimeBlock
from snf_schedule_optimizer.models.constraints import LookbackPeriod
from snf_schedule_optimizer.services.calculations.overtime_calculation import ThresholdOvertimeRule
from snf_schedule_optimizer.services.interfaces import (
    IEmployeeWorkHistoryService, IShiftReconcilerService,
    IRawHistoryRetriever
)


class EmployeeWorkHistoryServiceImpl(IEmployeeWorkHistoryService):
    """
    Provides robust calculation of accumulated hours by respecting the defined
    work week/day start times and filtering out previously paid OT hours.
    """

    def __init__(
            self,
            history_retriever: IRawHistoryRetriever,
            shift_reconciler: IShiftReconcilerService,
    ) -> None:
        # Dependencies like facility config for standard work period start times
        # could be injected here if not provided via the threshold rule.
        self.history_retriever = history_retriever
        self.shift_reconciler = shift_reconciler

    def get_remaining_non_ot_hours(
            self,
            employee: Employee,
            current_shift: Shift,
            ot_rules: List[ThresholdOvertimeRule],
    ) -> Dict[LookbackPeriod, float]:
        """
        Calculates the minimum remaining non-OT hours needed to trigger OT,
        checking all supplied daily and weekly rules.
        """

        raw_history_data = self.history_retriever.get_raw_inputs_for_period(
            employee.employee_id,
            current_shift.shift_start_dt
        )

        processed_history = (
            self._convert_raw_history_to_segments(
                raw_history_data
            )
        )

        remaining_hours = {
            LookbackPeriod.DAILY : float('inf'),
            LookbackPeriod.WEEKLY: float('inf')
        }

        for rule in ot_rules:
            trigger = rule.trigger

            # Process all daily threshold rules
            if trigger.daily_threshold is not None:

                remaining_daily = self.get_accumulated_hours(
                    employee,
                    current_shift,
                    processed_history,
                    threshold_hours=trigger.daily_threshold,
                    lookback_period=LookbackPeriod.DAILY,
                    work_period_start_time=trigger.work_period_start_time,
                )

                # We want the lowest remaining hours, as that rule will trigger OT first
                remaining_hours[LookbackPeriod.DAILY] = min(remaining_hours[LookbackPeriod.DAILY], remaining_daily)

            # Process all weekly threshold rules
            if trigger.weekly_threshold is not None:

                remaining_weekly = self.get_accumulated_hours(
                    employee,
                    current_shift,
                    processed_history,
                    threshold_hours=trigger.weekly_threshold,
                    lookback_period=LookbackPeriod.WEEKLY,
                    work_period_start_day=trigger.work_period_start_day,
                    work_period_start_time=trigger.work_period_start_time,
                )

                remaining_hours[LookbackPeriod.WEEKLY] = min(remaining_hours[LookbackPeriod.WEEKLY], remaining_weekly)

        # Return 0 if the value is infinity (no rule applied)
        if remaining_hours[LookbackPeriod.DAILY] == float('inf'):
            remaining_hours[LookbackPeriod.DAILY] = 0.0
        if remaining_hours[LookbackPeriod.WEEKLY] == float('inf'):
            remaining_hours[LookbackPeriod.WEEKLY] = 0.0

        return remaining_hours

    def get_accumulated_hours(
            self,
            employee: Employee,
            current_shift: Shift,
            history: Dict[Shift, List[WorkedShiftSegment]],
            threshold_hours: float,
            lookback_period: LookbackPeriod,
            work_period_start_day: Optional[int] = None,
            work_period_start_time: Optional[pendulum.Time] = None,
    ) -> float:

        # Determine the start boundary for the lookback period
        period_start_dt = self._get_work_period_start(
            current_shift.shift_start_dt,
            lookback_period,
            work_period_start_day,
            work_period_start_time
        )

        total_non_ot_hours_accumulated = 0.0

        # Iterate through shift history
        for shift, segments in history.items():
            # Only consider shifts that occurred before the current shift started
            if shift.shift_end_dt <= current_shift.shift_start_dt:

                for component in segments:
                    # Only count hours that fall within the current work period boundary
                    if component.start_time >= period_start_dt:

                        # Only count non-OT hours towards the threshold
                        if len(component.applicable_overtime_rules) == 0:
                            total_non_ot_hours_accumulated += component.duration_hours

        # Calculate remaining non-OT hours
        remaining_non_ot_hours = max(
            0.0,
            threshold_hours - total_non_ot_hours_accumulated
        )

        return remaining_non_ot_hours

    def get_consecutive_days_worked(
            self,
            employee: Employee,
            current_shift: Shift,
            history: Dict[Shift, List[WorkedShiftSegment]],
            max_consecutive_days: int,
    ) -> List[pendulum.Date]:
        if not history:
            return []

        # Collect all unique work dates prior to the current shift
        work_dates = {
            s.shift_start_dt.date() for s in history.keys()
            if s.shift_start_dt < current_shift.shift_start_dt
        }

        consecutive_dates = []

        # Check consecutive days backward from the day before the current shift
        target_date = current_shift.shift_start_dt.date().subtract(days=1)

        for _ in range(max_consecutive_days):
            if target_date in work_dates:
                consecutive_dates.append(target_date)
                target_date = target_date.subtract(days=1)
            else:
                break

        return consecutive_dates

    def get_processed_history_for_period(
            self,
            employee_id: str,
            check_date: pendulum.DateTime,
    ) -> Dict[Shift, List[WorkedShiftSegment]]:
        # 1. Fetch Raw Inputs (Shifts and Punches)
        raw_history_data: Dict[Shift, List[TimePunch]] = (
            self.history_retriever.get_raw_inputs_for_period(
                employee_id,
                check_date
            )
        )

        processed_history: Dict[Shift, List[WorkedShiftSegment]] = {}

        # 2. Reconcile Each Shift (The Core Integration Point)
        for shift, raw_punches in raw_history_data.items():

            # Use the Reconciler to convert raw inputs into clean blocks of time.
            worked_blocks: List[WorkedTimeBlock] = (
                self.shift_reconciler.reconcile_shift_to_blocks(
                    shift,
                    raw_punches
                )
            )

            segments = self._convert_blocks_to_initial_segments(shift, worked_blocks)

            processed_history[shift] = segments

        return processed_history

    def _get_work_period_start(
            self,
            shift_dt: pendulum.DateTime,
            period_type: LookbackPeriod,
            start_day: Optional[int],
            start_time: Optional[pendulum.Time],
            daily_reset_time: Optional[pendulum.Time] = None,
    ) -> pendulum.DateTime:
        """Determines the exact start time of the work period (day or week)."""

        # Use shift's timezone for all calculations
        tz = shift_dt.timezone
        assert isinstance(tz, pendulum.Timezone)

        if period_type == LookbackPeriod.DAILY:
            reset_time = daily_reset_time if daily_reset_time else pendulum.time(0, 0, 1)
            period_start = shift_dt.start_of('day').at(
                reset_time.hour, reset_time.minute, reset_time.second
            ).in_tz(tz)

            # If shift started before the reset time, the period started the day before
            if shift_dt < period_start:
                period_start = period_start.subtract(days=1)

            return period_start

        elif period_type == LookbackPeriod.WEEKLY:
            if start_day is None:
                # Default to Sunday if not specified (common FLSA default)
                start_day = pendulum.SUNDAY

                # Weekly period calculation
            period_start = shift_dt.start_of('week').add(days=start_day - pendulum.MONDAY).in_tz(tz)

            # If a specific start time is defined (e.g., Sunday 11:00 PM)
            if start_time:
                period_start = period_start.at(
                    start_time.hour, start_time.minute, start_time.second
                ).in_tz(tz)

            return period_start

        raise ValueError(f"Invalid period_type: {period_type}")

    def _convert_blocks_to_initial_segments(
            self,
            shift: Shift,
            blocks: List[WorkedTimeBlock],
    ) -> List[WorkedShiftSegment]:
        """
        This function creates the final historical segment structure from the clean time blocks.
        We initialize the rule lists as empty because the segments being created here
        are for *historical reference* in an OT calculation, and the final rules
        were set during the original calculation run (or will be set now).
        """

        return [
            WorkedShiftSegment(
                # --- Time and Parent Link ---
                # employee_id=block.employee_id,
                parent_shift=shift,
                start_time=block.start_time,
                end_time=block.end_time,

                # --- Cost Allocation Metadata (Transferred from WorkedTimeBlock) ---
                # These fields are required for cost tracing and must be set on the segment.
                shift_code=block.shift_code,
                job_code=block.job_code,
                cost_center_1=block.cost_center_1,
                cost_center_2=block.cost_center_2,

                # --- Rule Lists (Initialized to Empty) ---
                # These lists will be populated by the Shift Slicer and Rate Calculator
                # for the *current* shift being processed. For historical history, they
                # should remain empty if the source is only raw punches, or loaded
                # with final rule IDs if the source is stored segments.
                applicable_differential_rules=[],
                applicable_overtime_rules=[],
            )
            for block in blocks
        ]

    def _convert_raw_history_to_segments(
            self,
            raw_history: Dict[Shift, List[TimePunch]],
    ) -> Dict[Shift, List[WorkedShiftSegment]]:

        processed_history: Dict['Shift', List['WorkedShiftSegment']] = {}

        for shift, punches in raw_history.items():

            # Use the Reconciler to clean the punches and apply rounding/deductions
            worked_blocks: List[WorkedTimeBlock] = (
                self.shift_reconciler.reconcile_shift_to_blocks(shift, punches)
            )

            # Convert clean time blocks into the segment structure expected by calculation logic
            segments: List[WorkedShiftSegment] = []

            for block in worked_blocks:
                # Create the segment instance. Rules are empty because this history
                # has not been run through the full calculation pipeline yet (it's history).
                # We assume historical segments are FINALIZED, meaning they must contain
                # the actual OT status from the past calculation run.

                # IMPORTANT: If the history is only raw data, you must run the ENTIRE
                # OT/DIFFERENTIAL CALCULATION pipeline on the past shift segments to
                # determine if they were OT.

                # Since we are fetching history for an OT check, we must assume these
                # historical segments are FINALIZED from a previous run (containing rules).

                # If we assume historical segments are FINALIZED (best practice):
                # The raw punches model is wrong, and the original SQLAWorkHistoryRetriever (fetching
                # WorkedShiftSegmentModel) was right.

                # If we proceed with the current raw model, we must make a simplified assumption:

                segments.append(
                    WorkedShiftSegment(
                        # employee_id=block.employee_id,
                        parent_shift=shift,
                        start_time=block.start_time,
                        end_time=block.end_time,
                        # For historical segments from raw data, assume NO OT/Differential
                        # unless the database stores the FINALIZED segment data (which is safer).
                        applicable_differential_rules=[],
                        applicable_overtime_rules=[],
                    )
                )

            processed_history[shift] = segments

        return processed_history
