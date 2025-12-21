import whenever

from snf_schedule_optimizer.models import (
    Employee,
    Shift,
    ShiftKey,
    TimePunch,
    WorkedShiftSegment,
    WorkedTimeBlock,
)
from snf_schedule_optimizer.models.constraints import LookbackPeriod
from snf_schedule_optimizer.services.payroll.calculations.overtime_calculation import (
    ThresholdOvertimeRule,
)
from snf_schedule_optimizer.services.payroll.interfaces import IShiftReconcilerService
from snf_schedule_optimizer.services.repositories import (
    IFacilityRetriever,
    IShiftRetriever,
)
from snf_schedule_optimizer.services.timekeeping.interfaces import (
    IEmployeeWorkHistoryService,
    IRawHistoryRetriever,
)


class EmployeeWorkHistoryServiceImpl(IEmployeeWorkHistoryService):
    """
    Provides robust calculation of accumulated hours by respecting the defined
    work week/day start times and filtering out previously paid OT hours.
    """

    def __init__(
        self,
        history_retriever: IRawHistoryRetriever,
        shift_retriever: IShiftRetriever,
        shift_reconciler: IShiftReconcilerService,
        facility_config_retriever: IFacilityRetriever,
    ) -> None:
        # Dependencies like facility config for standard work period start times
        # could be injected here if not provided via the threshold rule.
        self.history_retriever = history_retriever
        self.shift_retriever = shift_retriever
        self.shift_reconciler = shift_reconciler
        self.facility_config_retriever = facility_config_retriever

    async def get_remaining_non_ot_hours(
        self,
        employee: Employee,
        current_shift: Shift,
        ot_rules: list[ThresholdOvertimeRule],
    ) -> dict[LookbackPeriod, float]:
        """
        Calculates the minimum remaining non-OT hours needed to trigger OT,
        checking all supplied daily and weekly rules.
        """

        facility_configs = await self.facility_config_retriever.get_configs(
            current_shift.org_id
        )
        facility_tzs = {fc.facility_id: fc.tz for fc in facility_configs}

        raw_history_data_per_key = (
            await self.history_retriever.get_raw_inputs_for_period(
                org_id=current_shift.org_id,
                employee_id=employee.employee_id,
                check_date=current_shift.shift_start_dt.to_instant(),
                facility_timezones=facility_tzs,
                facility_id=current_shift.facility_id,
            )
        )

        shifts: dict[ShiftKey, Shift] = await self.shift_retriever.get_shifts_by_keys(
            list(raw_history_data_per_key.keys()),
            facility_timezones=facility_tzs,
            org_id=current_shift.org_id,
        )

        processed_history = await self._convert_raw_history_to_segments(
            raw_history_data_per_key,
            shifts,
        )

        remaining_hours = {
            LookbackPeriod.DAILY: float("inf"),
            LookbackPeriod.WEEKLY: float("inf"),
        }

        for rule in ot_rules:
            trigger = rule.trigger

            # Process all daily threshold rules
            if trigger.daily_threshold is not None:
                remaining_daily = await self.get_accumulated_hours(
                    employee,
                    current_shift,
                    processed_history,
                    threshold_hours=trigger.daily_threshold,
                    lookback_period=LookbackPeriod.DAILY,
                    work_period_start_time=trigger.work_period_start_time,
                )

                # We want the lowest remaining hours, as that rule will trigger OT first
                remaining_hours[LookbackPeriod.DAILY] = min(
                    remaining_hours[LookbackPeriod.DAILY], remaining_daily
                )

            # Process all weekly threshold rules
            if trigger.weekly_threshold is not None:
                remaining_weekly = await self.get_accumulated_hours(
                    employee,
                    current_shift,
                    processed_history,
                    threshold_hours=trigger.weekly_threshold,
                    lookback_period=LookbackPeriod.WEEKLY,
                    work_period_start_day=trigger.work_period_start_day,
                    work_period_start_time=trigger.work_period_start_time,
                )

                remaining_hours[LookbackPeriod.WEEKLY] = min(
                    remaining_hours[LookbackPeriod.WEEKLY], remaining_weekly
                )

        # Return 0 if the value is infinity (no rule applied)
        if remaining_hours[LookbackPeriod.DAILY] == float("inf"):
            remaining_hours[LookbackPeriod.DAILY] = 0.0
        if remaining_hours[LookbackPeriod.WEEKLY] == float("inf"):
            remaining_hours[LookbackPeriod.WEEKLY] = 0.0

        return remaining_hours

    async def get_accumulated_hours(
        self,
        employee: Employee,
        current_shift: Shift,
        history: dict[ShiftKey, list[WorkedShiftSegment]],
        threshold_hours: float,
        lookback_period: LookbackPeriod,
        work_period_start_day: whenever.Weekday | None = None,
        work_period_start_time: whenever.Time | None = None,
    ) -> float:
        # Determine the start boundary for the lookback period
        period_start_dt = self._get_work_period_start(
            current_shift.shift_start_dt,
            lookback_period,
            work_period_start_day,
            work_period_start_time,
        )

        total_non_ot_hours_accumulated = 0.0

        # Retrieve facility timezones to hydrate shift objects
        facility_ids = list({k.facility_id for k in history})
        configs = await self.facility_config_retriever.get_configs(
            current_shift.org_id, facility_ids
        )
        tz_map = {c.facility_id: c.tz for c in configs}

        shifts = await self.shift_retriever.get_shifts_by_keys(
            list(history.keys()),
            facility_timezones=tz_map,
            org_id=current_shift.org_id,
        )

        # Iterate through shift history
        for shift_key, segments in history.items():
            shift = shifts.get(shift_key)
            if not shift:
                raise ValueError(
                    f"Shift not found for key {shift_key} while calculating accumulated hours."
                )
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
            0.0, threshold_hours - total_non_ot_hours_accumulated
        )

        return remaining_non_ot_hours

    def get_consecutive_days_worked(
        self,
        employee: Employee,
        current_shift: Shift,
        history: dict[Shift, list[WorkedShiftSegment]],
        max_consecutive_days: int,
    ) -> list[whenever.Date]:
        if not history:
            return []

        # Collect all unique work dates prior to the current shift
        work_dates = {
            s.shift_start_dt.date()
            for s in history
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

    async def get_processed_history_for_period(
        self,
        org_id: str,
        employee_id: str,
        check_date: whenever.Instant,
        facility_id: str | None = None,
    ) -> dict[ShiftKey, list[WorkedShiftSegment]]:
        facility_ids = [facility_id] if facility_id else None
        configs = await self.facility_config_retriever.get_configs(org_id, facility_ids)

        facility_tzs = {c.facility_id: c.tz for c in configs}

        # 1. Fetch Raw Inputs (Shifts and Punches)
        raw_history_data: dict[
            ShiftKey, list[TimePunch]
        ] = await self.history_retriever.get_raw_inputs_for_period(
            org_id=org_id,
            employee_id=employee_id,
            check_date=check_date,
            facility_timezones=facility_tzs,
            facility_id=facility_id,
        )

        if not raw_history_data:
            return {}

        tz_map = {c.facility_id: c.tz for c in configs}

        shifts = await self.shift_retriever.get_shifts_by_keys(
            shift_keys=list(raw_history_data.keys()),
            facility_timezones=tz_map,
            org_id=org_id,
        )

        processed_history = await self._convert_raw_history_to_segments(
            raw_history_data, shifts
        )

        return processed_history

    def _get_work_period_start(
        self,
        shift_dt: whenever.ZonedDateTime,
        period_type: LookbackPeriod,
        start_day: whenever.Weekday | None,
        period_start_time: whenever.Time | None = None,
    ) -> whenever.ZonedDateTime:
        """
        Determines the exact start datetime of the work period (day or week) relative to the shift.

        Args:
            shift_dt: The timestamp of the shift being evaluated.
            period_type: Whether to calculate the start of the Day or the Week.
            start_day: (Weekly only) The day of the week the work week begins (e.g., Sunday).
            period_start_time: The time of day the period begins.
                               For DAILY: The start of the workday (e.g., 7:00 AM).
                               For WEEKLY: The time on start_day the week begins (e.g., Sun 11:00 PM).
        """

        if period_type == LookbackPeriod.DAILY:
            # For daily calculation, we determine when the "work day" containing this shift started.
            # If period_start_time is None, assume midnight (00:00:00).
            reset_time = period_start_time or whenever.Time(0, 0, 0)

            # Use 'replace_time' to set time on the date
            period_start = shift_dt.replace_time(reset_time)

            # If shift started before the reset time (e.g. shift at 3am, reset at 7am),
            # this shift belongs to the *previous* operational day.
            if shift_dt < period_start:
                period_start = period_start.subtract(days=1)

            return period_start

        elif period_type == LookbackPeriod.WEEKLY:
            if start_day is None:
                # Default to Sunday if not specified (common FLSA default)
                start_day = whenever.SUNDAY

            # Reset to start of the current day at 00:00
            period_start = shift_dt.replace_time(whenever.Time(0, 0, 0))

            # Walk back to the start day
            while period_start.date().day_of_week() != start_day:
                period_start = period_start.subtract(days=1)

            # 3. Apply the specific start time (e.g., 11:00 PM on that start day)
            if period_start_time:
                period_start = period_start.replace_time(period_start_time)

                # Edge case: If the shift is on the Start Day but BEFORE the Start Time
                # (e.g., Shift is Sunday 8pm, Week starts Sunday 11pm),
                # then this shift belongs to the *previous* week.
                if shift_dt < period_start:
                    period_start = period_start.subtract(weeks=1)

            return period_start

        raise ValueError(f"Invalid period_type: {period_type}")

    def _convert_blocks_to_initial_segments(
        self,
        shift: Shift,
        blocks: list[WorkedTimeBlock],
    ) -> list[WorkedShiftSegment]:
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

    async def _convert_raw_history_to_segments(
        self,
        raw_history: dict[ShiftKey, list[TimePunch]],
        shifts: dict[ShiftKey, Shift],
    ) -> dict[ShiftKey, list[WorkedShiftSegment]]:
        processed_history: dict[ShiftKey, list[WorkedShiftSegment]] = {}

        for shift_key, punches in raw_history.items():
            shift = shifts.get(shift_key)
            if not shift:
                raise ValueError(
                    f"Shift not found for key {shift_key} while processing history."
                )

            # Use the Reconciler to clean the punches and apply rounding/deductions
            worked_blocks: list[
                WorkedTimeBlock
            ] = await self.shift_reconciler.reconcile_shift_to_blocks(shift, punches)

            # Convert clean time blocks into the segment structure expected by calculation logic
            segments: list[WorkedShiftSegment] = []

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

            processed_history[shift.shift_key] = segments

        return processed_history
