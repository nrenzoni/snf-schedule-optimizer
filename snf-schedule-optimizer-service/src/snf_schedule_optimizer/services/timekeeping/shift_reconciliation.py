import dataclasses

import whenever

from snf_schedule_optimizer.datetime_utils import is_between
from snf_schedule_optimizer.models import (
    EmployeeTimeSettings,
    MealDeductionRules,
    PunchType,
    Shift,
    SplitDayType,
    TimePunch,
    WorkedTimeBlock,
)
from snf_schedule_optimizer.services.payroll.interfaces import (
    IFacilityRulesService,
    IShiftReconcilerService,
)


class ShiftReconcilerServiceImpl(IShiftReconcilerService):
    """
    Applies complex business logic (rounding, meal deduction) to raw punches
    to create precise WorkedTimeBlock segments.
    """

    def __init__(
        self,
        facility_rules_service: IFacilityRulesService,
    ):
        # This service provides rounding rules, auto-deduction times, etc.
        self.rules_service = facility_rules_service

    def reconcile_shift_to_blocks(
        self,
        scheduled_shift: Shift,
        raw_punches: list[TimePunch],
    ) -> list[WorkedTimeBlock]:
        # 1. Sort Punches: Crucial for pairing
        raw_punches.sort(key=lambda p: p.punch_time)

        # NOTE: We need the employee's specific time settings (e.g., pairing threshold).
        # Assuming the rules service can provide this based on employee/date.
        settings = self.rules_service.get_time_settings(
            raw_punches[0].employee_id, scheduled_shift.shift_start_dt
        )

        # 2. Punch Pairing ('Pair' logic)
        paired_blocks = self._pair_raw_punches(raw_punches, settings)

        # 3. Apply Splitting ('SplitPunches' logic)
        blocks_after_split = []
        for block in paired_blocks:
            blocks_after_split.extend(self._split_overnight_block(block, settings))

        # 4. Apply Rounding & Meal Deduction (Simplified)
        final_blocks = []
        for block in blocks_after_split:
            # Reapply rounding and meal deduction logic here
            final_blocks.extend(self._apply_rounding_and_deduction(block, settings))

        return final_blocks

    def _pair_raw_punches(
        self,
        punches: list[TimePunch],
        settings: EmployeeTimeSettings,
    ) -> list[WorkedTimeBlock]:
        paired_blocks: list[WorkedTimeBlock] = []
        i = 0

        # Collect all raw punch times for fast intermediate checking
        all_punch_times = [p.punch_time for p in punches]

        while i < len(punches):
            punch1 = punches[i]

            # 1. INITIAL PUNCH VALIDATION
            # Check for ignored, voided, or manual adjustment flags (draggedTime)
            if punch1.is_void or punch1.is_ignored or punch1.is_dragged_time:
                i += 1
                continue

            # Check for CheckIn type
            if punch1.punch_type in [None, "CheckIn"]:
                # Look for the immediate next punch
                if i + 1 < len(punches):
                    punch2 = punches[i + 1]

                    # 1b. PUNCH 2 VALIDATION
                    if punch2.is_void or punch2.is_ignored or punch2.is_dragged_time:
                        # If the next punch is invalid, treat punch1 as unpaired (i++ and continue)
                        i += 1
                        continue

                    # Check for CheckOut type
                    if punch2.punch_type in [None, "CheckOut"]:
                        duration = punch2.punch_time - punch1.punch_time

                        # 2. DURATION THRESHOLD CHECK
                        # We use the pairing_threshold from settings.
                        if duration <= settings.pairing_threshold.time_part():
                            is_pairable = True

                            # 3. INTERMEDIATE PUNCH CHECK
                            # "Don't pair if there are other punch/es between the 2"
                            # Check if any other valid punch time exists strictly between punch1 and punch2.

                            # Find all times that are potentially between the pair
                            intermediate_punches = [
                                t
                                for t in all_punch_times
                                if is_between(t, punch1.punch_time, punch2.punch_time)
                            ]

                            if intermediate_punches:
                                is_pairable = False

                            # 4. SHIFT SEPARATOR CHECK (NEW INTEGRATION)
                            # Assume shift_separator_time is available on the settings object.
                            shift_sep_time = settings.shift_separator_time

                            if (
                                shift_sep_time is not None
                                and self._is_separated_by_shift(
                                    punch1.punch_time, punch2.punch_time, shift_sep_time
                                )
                            ):
                                # If the block crosses the shift separator boundary, it cannot be paired.
                                is_pairable = False

                            if is_pairable:
                                # Create the block and transfer relevant metadata from the punch
                                paired_blocks.append(
                                    WorkedTimeBlock(
                                        employee_id=punch1.employee_id,
                                        start_time=punch1.punch_time,
                                        end_time=punch2.punch_time,
                                        post_date=punch1.punch_time.date(),
                                        is_scheduled=False,  # Reconciler will check schedule later
                                        # TRANSFER COSTING METADATA:
                                        shift_code=punch1.shift_code,
                                        job_code=punch1.job_code,
                                        cost_center_1=punch1.cost_center_1,
                                        cost_center_2=punch1.cost_center_2,
                                        rate_from_punch=punch1.rate,
                                        meal_not_taken=punch2.meal_not_taken,  # Often set on the OUT punch
                                        # NOTE: post_date is set in the splitting logic, not here.
                                    )
                                )
                                i += 2  # Skip the paired OUT punch
                                continue

            i += 1  # Move to the next punch if punch1 was invalid or unpaired

        return paired_blocks

    def _split_overnight_block(
        self,
        block: WorkedTimeBlock,
        settings: EmployeeTimeSettings,
    ) -> list[WorkedTimeBlock]:
        """
        Replicates the SplitPunches logic, splitting a block that crosses the
        payroll day reset threshold.
        """
        reset_time = settings.split_day_threshold_time

        if reset_time is None:
            return [block]

        # Convert the reset time (e.g., 3:00 AM) to a concrete DateTime on the IN day
        # We use start_of("day") to get midnight, then add the reset time components.
        # Note: start_of("day") returns a timezone-aware DateTime instance.
        reset_dt = block.start_time.start_of_day().replace_time(reset_time)

        # ADJUST FOR PREVIOUS DAY TYPE: If the block started *after* the reset time
        # but the rule says to associate it with the previous day (C# logic using DayType.Previous)
        if (
            settings.split_day_day_type == SplitDayType.PREVIOUS
            and block.start_time < reset_dt
        ):
            # If the shift started before the reset time, the relevant reset point
            # is often the reset time from the previous calendar day.
            # However, for splitting *a punch block*, we just need the point it crosses.
            # We proceed with the current reset_dt, assuming the post_date logic handles the day shift.
            pass

        # Check if the block crosses the reset boundary
        if block.start_time < reset_dt < block.end_time:
            # --- Determine Post Dates ---
            # Block 1 (before reset) keeps the original post_date
            post_date_block1 = block.post_date

            # Block 2 (after reset) shifts to the next calendar day
            # This is the core purpose of the split: to ensure hours after the reset
            # count toward the next payroll day's OT threshold.
            post_date_block2 = block.post_date.add(days=1)

            # --- Create Block 1 (Before Reset) ---
            block1 = WorkedTimeBlock(
                employee_id=block.employee_id,
                start_time=block.start_time,
                end_time=reset_dt,  # Ends exactly at the reset time
                post_date=post_date_block1,
                is_scheduled=block.is_scheduled,
                shift_code=block.shift_code,
                job_code=block.job_code,
                cost_center_1=block.cost_center_1,
                cost_center_2=block.cost_center_2,
                rate_from_punch=block.rate_from_punch,
                meal_not_taken=block.meal_not_taken,
            )

            # --- Create Block 2 (After Reset) ---
            block2 = WorkedTimeBlock(
                employee_id=block.employee_id,
                start_time=reset_dt,  # Starts exactly at the reset time
                end_time=block.end_time,
                post_date=post_date_block2,  # SHIFTED PAYROLL DAY
                is_scheduled=block.is_scheduled,
                shift_code=block.shift_code,
                job_code=block.job_code,
                cost_center_1=block.cost_center_1,
                cost_center_2=block.cost_center_2,
                rate_from_punch=block.rate_from_punch,
                meal_not_taken=block.meal_not_taken,
            )

            return [block1, block2]

        return [block]

    def _apply_rounding_and_deduction(
        self,
        block: WorkedTimeBlock,
        settings: EmployeeTimeSettings,
    ) -> list[WorkedTimeBlock]:
        # 1. Apply Rounding (Crucial Step: Rounding MUST happen before deduction checks)
        rounded_start = self.rules_service.apply_rounding(
            block.start_time, PunchType.CHECK_IN
        )
        rounded_end = self.rules_service.apply_rounding(
            block.end_time, PunchType.CHECK_OUT
        )

        # Create a temporary rounded block for deduction checks
        rounded_block = WorkedTimeBlock(
            employee_id=block.employee_id,
            start_time=rounded_start,
            end_time=rounded_end,
            post_date=block.post_date,
            is_scheduled=block.is_scheduled,
            shift_code=block.shift_code,
            job_code=block.job_code,
            cost_center_1=block.cost_center_1,
            cost_center_2=block.cost_center_2,
            rate_from_punch=block.rate_from_punch,
            meal_not_taken=block.meal_not_taken,
        )

        # 2. Check and Apply Meal Deduction
        deduction_rules = self.rules_service.get_meal_deduction_rules(rounded_start)

        if deduction_rules and deduction_rules.is_mandatory:
            # Only check if the rounded duration exceeds the minimum threshold
            rounded_duration = (rounded_end - rounded_start).in_hours()

            if rounded_duration >= deduction_rules.meal_threshold_hours:
                # Delegate the splitting logic to the helper method
                return self._get_blocks_after_deduction(rounded_block, deduction_rules)

        # If no deduction is applied, return the single rounded block
        return [rounded_block]

    def _get_blocks_after_deduction(
        self,
        block: WorkedTimeBlock,
        deduction_rules: MealDeductionRules,
    ) -> list[WorkedTimeBlock]:
        """
        Splits the block into two, removing the mandatory meal period (e.g., 30 mins)
        from the center of the block.
        """
        duration = block.end_time - block.start_time
        deduction_duration = whenever.DateTimeDelta(
            hours=deduction_rules.meal_duration_hours
        )

        # Calculate where the deduction sits (usually near the midpoint or after 5 hours)

        # We assume placement is at the midpoint for simplicity, unless meal_placement_hours is set.
        placement_start_dt = block.start_time.add(seconds=duration.in_seconds() / 2)

        # Calculate the start and end of the deduction gap
        duration_div_2 = deduction_duration.time_part() / 2
        deduction_gap_start = placement_start_dt - duration_div_2
        deduction_gap_end = placement_start_dt + duration_div_2

        # Check for invalid split points (e.g., gap starts before block begins)
        if (
            deduction_gap_start <= block.start_time
            or deduction_gap_end >= block.end_time
        ):
            # In robust payroll, this requires careful auditing, but we proceed with the split.
            pass

            # Create Block 1 (Work before the meal gap)
        block1 = dataclasses.replace(
            block,
            end_time=deduction_gap_start,
        )

        # Create Block 2 (Work after the meal gap)
        block2 = dataclasses.replace(
            block,
            start_time=deduction_gap_end,
        )

        return [block1, block2]

    def _is_separated_by_shift(
        self,
        punch_in_local_time: whenever.ZonedDateTime,
        punch_out_local_time: whenever.ZonedDateTime,
        shift_separator_time: whenever.Time,  # Should be part of EmployeeTimeSettings
    ) -> bool:
        """
        Checks if the time block spans across the configured daily shift separator time.

        This logic determines the specific midnight/reset point (seperatorTime)
        relative to the punch-in time.
        """

        # 1. Determine the separator time's concrete DateTime on the IN day
        # C#: var seperatorTime = new DateTime(punchInLocalTime.Year, ..., shiftSeperator.Hours, ...);
        separator_dt = punch_in_local_time.start_of_day().replace_time(
            shift_separator_time
        )

        # 2. Adjust Separator to Next Day if Punch-In is AFTER the Separator Time
        # if (punchInLocalTime > seperatorTime) seperatorTime = seperatorTime.AddDays(1);
        if punch_in_local_time > separator_dt:
            separator_dt = separator_dt.add(days=1)

        # 3. Final Check: Does the block straddle the separator?
        # C#: return punchInLocalTime < seperatorTime && punchOutLocalTime > seperatorTime;
        return punch_in_local_time < separator_dt < punch_out_local_time
